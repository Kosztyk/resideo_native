"""Public-client B2C / PKCE authentication recovered from Resideo Android 6.21.1.

No developer credentials, password-grant guesses, or SmartThings tokens are used.
Passwords are sent only to Resideo's B2C sign-in page and are never retained.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import SplitResult, parse_qs, urlencode, urljoin, urlsplit

import aiohttp

from .errors import (
    AuthenticationError,
    CannotConnect,
    InteractionRequired,
    InvalidCallback,
    InvalidResponse,
    RateLimited,
)

AUTHORITY = "https://lyricprod.b2clogin.com/lyricprod.onmicrosoft.com"
CLIENT_ID = "d7baddb4-d9f3-4575-af28-f1b04a7883f2"
POLICY = "b2c_1a_signin_mob_hh"
REDIRECT_URI = "com.honeywell.acs.lyric.enterprise://oauth2redirect"
SCOPE = (
    "https://lyricprod.onmicrosoft.com/CHILAPIService/user_impersonation "
    "profile email openid offline_access"
)
TIMEOUT = aiohttp.ClientTimeout(total=45)
USER_AGENT = "Lyric/6.21.1(HomeAssistant;Android 10)"


def is_native_callback(parsed: SplitResult) -> bool:
    """Allow the empty/root path browsers produce for the native app callback."""
    expected = urlsplit(REDIRECT_URI)
    return (
        parsed.scheme == expected.scheme
        and parsed.netloc == expected.netloc
        and parsed.path in ("", "/")
        and not parsed.fragment
    )


def retry_seconds(value: str | None) -> float:
    """Accept Retry-After in either HTTP format, with a useful default."""
    try:
        return max(1, float(value or 60))
    except ValueError:
        try:
            return max(1, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 60


@dataclass(repr=False)
class Token:
    """A refreshable authorization; repr intentionally hides all token material."""

    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: float

    @classmethod
    def from_storage(cls, value: dict[str, Any]) -> Token:
        try:
            access = value["access_token"]
            refresh = value["refresh_token"]
            if (
                not isinstance(access, str)
                or not access
                or not isinstance(refresh, str)
                or not refresh
            ):
                raise ValueError
            return cls(access, refresh, float(value["expires_at"]))
        except (KeyError, TypeError, ValueError) as err:
            raise AuthenticationError("Stored Resideo authorization is incomplete") from err

    def as_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }


class ResideoAuth:
    """Handle authorization-code sign-in and serialized rotating refresh tokens."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: Token | None = None,
        on_token: Callable[[Token], None] | None = None,
    ) -> None:
        self.session = session
        self.token = token
        self.on_token = on_token
        self._lock = asyncio.Lock()
        self._retry_at = 0.0

    @staticmethod
    def new_authorization(country: str = "RO") -> dict[str, str]:
        """Generate a fresh authorization, verifier, state, and native callback."""
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(24)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        params = {
            "p": POLICY,
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "response_type": "code",
            "state": state,
            "nonce": secrets.token_urlsafe(16),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "ui_locales": "en-US",
            "country": country,
            "enableContractor": "false",
            "prompt": "login",
        }
        return {
            "url": AUTHORITY + "/oauth2/v2.0/authorize?" + urlencode(params),
            "verifier": verifier,
            "state": state,
        }

    @staticmethod
    def read_settings(page: str) -> dict[str, Any]:
        """Read B2C's JSON settings without evaluating JavaScript."""
        match = re.search(r"\bvar\s+SETTINGS\s*=\s*", page)
        if not match:
            raise InteractionRequired("Resideo requires browser sign-in")
        try:
            settings, _ = json.JSONDecoder().raw_decode(page[match.end() :])
            hosts = settings["hosts"]
            tenant = hosts["tenant"]
            if (
                not isinstance(settings["csrf"], str)
                or not isinstance(settings["transId"], str)
                or settings["api"] != "CombinedSigninAndSignup"
                or not isinstance(tenant, str)
                or not tenant.startswith("/lyricprod.onmicrosoft.com/")
                or ":" in tenant
                or ".." in tenant
                or "?" in tenant
                or "#" in tenant
                or hosts["policy"].lower() != POLICY
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError, AttributeError) as err:
            raise InteractionRequired("Resideo requires browser sign-in") from err
        return settings

    async def login(self, username: str, password: str, country: str = "RO") -> Token:
        """Submit the actual hosted sign-in form, maintaining its CSRF cookies."""
        authorization = self.new_authorization(country)
        origin = urlsplit(AUTHORITY)
        # HA's shared HTTP session may use DummyCookieJar. A short-lived auth
        # session is required for B2C's anti-forgery cookies; never share them.
        async with aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(),
            timeout=TIMEOUT,
            trust_env=self.session.trust_env,
            headers={"User-Agent": USER_AGENT},
        ) as login_session:
            response, _, _ = await self._request(login_session, "GET", authorization["url"])
            settings = self.read_settings(response)
            tenant = settings["hosts"]["tenant"]
            base = f"{origin.scheme}://{origin.netloc}{tenant}"
            params = {"tx": settings["transId"], "p": settings["hosts"]["policy"]}
            text, status, _ = await self._request(
                login_session,
                "POST",
                base + "/SelfAsserted",
                params=params,
                headers={"X-CSRF-TOKEN": settings["csrf"], "Referer": authorization["url"]},
                data={"request_type": "RESPONSE", "signInName": username, "password": password},
            )
            try:
                result = json.loads(text)
            except (ValueError, TypeError) as err:
                raise InteractionRequired("Complete sign-in using the browser method") from err
            if status != 200 or not isinstance(result, dict) or str(result.get("status")) != "200":
                if isinstance(result, dict) and any(
                    term in str(result.get("message", "")).lower()
                    for term in (
                        "verification",
                        "captcha",
                        "multifactor",
                        "multi-factor",
                        "verify",
                        "eula",
                        "consent",
                    )
                ):
                    raise InteractionRequired("Complete verification in the browser sign-in method")
                raise AuthenticationError(
                    "Resideo rejected sign-in; check your account in the Resideo app"
                )
            confirmed = base + "/api/" + settings["api"] + "/confirmed"
            params["csrf_token"] = settings["csrf"]
            params["rememberMe"] = "false"
            callback = await self._finish_login(login_session, confirmed + "?" + urlencode(params))
        return await self.exchange_callback(callback, authorization)

    async def _finish_login(self, session: aiohttp.ClientSession, url: str) -> str:
        """Follow B2C-only redirects, stopping before the native app callback."""
        allowed_origin = urlsplit(AUTHORITY).netloc
        for _ in range(8):
            parsed = urlsplit(url)
            if is_native_callback(parsed):
                return url
            if parsed.scheme != urlsplit(AUTHORITY).scheme or parsed.netloc != allowed_origin:
                raise InvalidResponse("Unexpected redirect during Resideo sign-in")
            _, status, headers = await self._request(session, "GET", url)
            if status in (301, 302, 303, 307, 308) and headers.get("Location"):
                url = urljoin(url, headers["Location"])
                continue
            raise InteractionRequired(
                "Use browser sign-in to complete verification or accept updated terms"
            )
        raise InteractionRequired("Resideo sign-in did not finish; use browser sign-in")

    async def exchange_callback(self, callback: str, authorization: dict[str, str]) -> Token:
        try:
            parsed = urlsplit(callback.strip())
            if not is_native_callback(parsed):
                raise ValueError
            params = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=20)
        except ValueError as err:
            raise InvalidCallback("Paste the complete native Resideo redirect URL") from err
        state = params.get("state", [""])
        code = params.get("code", [""])
        if len(state) != 1 or not hmac.compare_digest(
            state[0].encode(), authorization["state"].encode()
        ):
            raise InvalidCallback("The sign-in belongs to a different setup attempt")
        if "error" in params:
            raise AuthenticationError("Resideo did not authorize sign-in")
        if len(code) != 1 or not code[0]:
            raise InvalidCallback("The complete Resideo redirect URL must contain one sign-in code")
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code[0],
                "code_verifier": authorization["verifier"],
            }
        )

    async def import_refresh_token(self, refresh_token: str) -> Token:
        """Accept only a token for this legacy Resideo app client, not First Alert."""
        return await self._token_request(
            {"grant_type": "refresh_token", "refresh_token": refresh_token.strip()}
        )

    async def access_token(self, rejected_token: str | None = None) -> str:
        async with self._lock:
            if not self.token or not self.token.refresh_token:
                raise AuthenticationError("Sign in to Resideo again")
            if rejected_token is not None and rejected_token != self.token.access_token:
                return self.token.access_token
            if rejected_token is not None or self.token.expires_at <= time.time() + 120:
                await self._token_request(
                    {"grant_type": "refresh_token", "refresh_token": self.token.refresh_token}
                )
            return self.token.access_token

    async def _token_request(self, grant: dict[str, str]) -> Token:
        text, status, _ = await self._request(
            self.session,
            "POST",
            AUTHORITY + "/oauth2/v2.0/token",
            params={"p": POLICY},
            data={"client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "scope": SCOPE, **grant},
        )
        try:
            data = json.loads(text)
        except (ValueError, TypeError) as err:
            raise CannotConnect("Resideo returned an invalid token response") from err
        if status in (400, 401, 403) or isinstance(data, dict) and data.get("error"):
            if isinstance(data, dict) and data.get("error") in (
                "temporarily_unavailable",
                "server_error",
            ):
                raise CannotConnect("Resideo sign-in is temporarily unavailable")
            raise AuthenticationError(
                "Resideo authorization expired or was rejected; sign in again"
            )
        if status != 200 or not isinstance(data, dict):
            raise CannotConnect("Resideo token request failed")
        refresh = data.get("refresh_token") or grant.get("refresh_token")
        access = data.get("access_token")
        try:
            lifetime = float(data["expires_in"])
            if (
                not isinstance(access, str)
                or not access
                or not isinstance(refresh, str)
                or not refresh
                or lifetime <= 0
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError) as err:
            raise InvalidResponse("Resideo did not return a refreshable authorization") from err
        self.token = Token(access, refresh, time.time() + lifetime)
        if self.on_token:
            self.on_token(self.token)
        return self.token

    async def _request(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> tuple[str, int, Any]:
        if self._retry_at > time.monotonic():
            raise RateLimited(self._retry_at - time.monotonic())
        try:
            async with session.request(
                method, url, timeout=TIMEOUT, allow_redirects=False, **kwargs
            ) as response:
                if response.status == 429:
                    pause = retry_seconds(response.headers.get("Retry-After"))
                    self._retry_at = time.monotonic() + pause
                    raise RateLimited(pause)
                if response.status >= 500:
                    raise CannotConnect("Resideo sign-in service is temporarily unavailable")
                return await response.text(), response.status, response.headers
        except (TimeoutError, aiohttp.ClientError) as err:
            raise CannotConnect("Cannot connect to Resideo sign-in service") from err
