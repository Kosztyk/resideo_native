"""Exercise real HTTP serialization and protocol behavior without an account."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sys
import time
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components/resideo_native"))

from protocol import (
    AuthenticationError,
    CannotConnect,
    CommandError,
    InteractionRequired,
    InvalidResponse,
    NativeClient,
    RateLimited,
    ResideoAuth,
    Token,
)
from protocol import auth as auth_module
from protocol import client as client_module
from protocol.device import parse_locations


def locations():
    """Synthetic data following the APK's Location/StatDevice response models."""
    return [
        {
            "locationID": 123,
            "name": "Test home",
            "devices": [
                {"deviceClass": "LeakDetector", "deviceID": "ignored"},
                {
                    "deviceClass": "Thermostat",
                    "deviceID": "T6-test",
                    "name": "Test thermostat",
                    "deviceType": "Jasper",
                    "deviceModel": "Jasper",
                    "isAlive": True,
                    "displayIndoorHumidity": False,
                    "thermostat": {
                        "units": "Celsius",
                        "indoorTemperature": 69.8,
                        "indoorHumidity": 128,
                        "allowedModes": ["Off", "Heat"],
                        "minHeatSetpoint": 41,
                        "maxHeatSetpoint": 95,
                        "operationStatus": {"mode": "Heat"},
                        "changeableValues": {
                            "mode": "Heat",
                            "heatSetpoint": 71.6,
                            "thermostatSetpointStatus": "NoHold",
                        },
                    },
                },
            ],
        }
    ]


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = []
        self.auth_codes = {}
        self.refresh_count = 0
        self.failures = {}
        self.cookie_verified = False
        self.opaque_b2c_cookies = False
        self.callback_path = ""
        self.login_redirects = 0
        self.login_redirect_status = 302
        self.login_redirect_target = None
        self.interactive_page = False
        self.credential_reply = None
        self.confirmation_reply = None
        self.payload = locations()
        self.app = web.Application()
        self.app.router.add_route("*", "/{tail:.*}", self.handle)
        self.server = TestServer(self.app, host="localhost")
        await self.server.start_server()
        self.root = str(self.server.make_url("/")).rstrip("/")
        self.authority = self.root + "/lyricprod.onmicrosoft.com"
        self.patches = [
            patch.object(auth_module, "AUTHORITY", self.authority),
            patch.object(client_module, "BASE_URL", self.root + "/"),
        ]
        for p in self.patches:
            p.start()
        self.session = aiohttp.ClientSession()
        self.auth = ResideoAuth(self.session, Token("valid", "refresh-initial", time.time() + 3600))
        self.client = NativeClient(self.session, self.auth)

    async def asyncTearDown(self):
        await self.session.close()
        await self.server.close()
        for p in self.patches:
            p.stop()

    async def handle(self, request):
        body = await request.read()
        self.calls.append((request.method, request.path, dict(request.headers), body))
        status = self.failures.get(request.path)
        if status:
            return web.json_response(
                {"private": "must-not-appear-in-errors"},
                status=status,
                headers={"Retry-After": "120"} if status == 429 else {},
            )
        if request.path.endswith("/authorize"):
            self.auth_codes["state"] = request.query["state"]
            self.auth_codes["challenge"] = request.query["code_challenge"]
            if self.login_redirects or self.login_redirect_target:
                response = web.Response(
                    status=self.login_redirect_status,
                    headers={"Location": self.login_redirect_target or "/signin/1"},
                )
                response.set_cookie("pre-login", "redirect-cookie")
                return response
            return self.login_page()
        if request.path.startswith("/signin/"):
            if request.cookies.get("pre-login") != "redirect-cookie":
                return web.Response(status=403)
            index = int(request.path.rsplit("/", 1)[-1])
            if index < self.login_redirects:
                return web.Response(
                    status=self.login_redirect_status,
                    headers={"Location": f"/signin/{index + 1}"},
                )
            return self.login_page()
        if self.opaque_b2c_cookies and request.path.endswith(("/SelfAsserted", "/confirmed")):
            # B2C rejects quoting added to its unquoted, padded cookie values.
            raw_cookies = request.headers.get("Cookie", "").split("; ")
            if not all(
                pair in raw_cookies
                for pair in (
                    "x-ms-cpim-trans=eyJ0cmFucyI6InRlc3QifQ==",
                    "x-ms-cpim-cache|test_0=YWJjL2RlZis/==",
                )
            ):
                return web.Response(status=400, text="Bad Request", content_type="text/html")
        if request.path.endswith("/SelfAsserted"):
            self.cookie_verified = request.cookies.get("x-ms-cpim-csrf") == "cookie-test"
            if not self.cookie_verified or request.headers.get("X-CSRF-TOKEN") != "csrf-test":
                return web.json_response({"status": "400"})
            form = parse_qs(body.decode())
            if form.get("password") != ["correct-password"]:
                return web.json_response(
                    {"status": "400", "message": "Incorrect password for private@example.test"}
                )
            if self.credential_reply is not None:
                if isinstance(self.credential_reply, dict):
                    return web.json_response(self.credential_reply)
                return web.Response(text=self.credential_reply)
            return web.json_response({"status": "200"})
        if request.path.endswith("/confirmed"):
            if self.confirmation_reply is not None:
                return web.Response(text=self.confirmation_reply)
            location = (
                auth_module.REDIRECT_URI
                + self.callback_path
                + "?"
                + urlencode({"code": "one-time-code", "state": self.auth_codes["state"]})
            )
            return web.Response(status=302, headers={"Location": location})
        if request.path.endswith("/token"):
            form = parse_qs(body.decode())
            if form["grant_type"] == ["authorization_code"]:
                verifier = form["code_verifier"][0]
                challenge = (
                    base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                    .decode()
                    .rstrip("=")
                )
                if challenge != self.auth_codes["challenge"]:
                    return web.json_response({"error": "invalid_grant"}, status=400)
            else:
                self.refresh_count += 1
            return web.json_response(
                {
                    "access_token": "valid",
                    "refresh_token": f"rotated-{self.refresh_count}",
                    "expires_in": 3600,
                }
            )
        if request.headers.get("Authorization") != "Bearer valid":
            return web.json_response({"error": "expired"}, status=401)
        if request.path == "/api/v2/session":
            return web.json_response(
                {
                    "user": {"userID": 456, "username": "private@example.test"},
                    "bodytoken": "not-to-be-logged",
                }
            )
        if request.path == "/api/v4/locations":
            return web.json_response(self.payload)
        if request.method in ("PUT", "POST") and request.path.startswith("/api/"):
            return web.Response(status=204)
        return web.Response(status=404)

    def login_page(self):
        if self.interactive_page:
            return web.Response(text="<html>Complete account verification</html>")
        settings = {
            "hosts": {
                "tenant": "/lyricprod.onmicrosoft.com/B2C_1A_SignIn_Mob_HH",
                "policy": "B2C_1A_SignIn_Mob_HH",
            },
            "csrf": "csrf-test",
            "transId": "StateProperties=test",
            "api": "CombinedSigninAndSignup",
        }
        response = web.Response(
            text="<html><script>var SETTINGS = " + json.dumps(settings) + ";</script></html>"
        )
        response.set_cookie("x-ms-cpim-csrf", "cookie-test")
        if self.opaque_b2c_cookies:
            # Raw Set-Cookie headers model the production service. set_cookie()
            # would itself quote the value and hide the client-side regression.
            response.headers.add(
                "Set-Cookie", "x-ms-cpim-trans=eyJ0cmFucyI6InRlc3QifQ==; Path=/; HttpOnly"
            )
            response.headers.add(
                "Set-Cookie", "x-ms-cpim-cache|test_0=YWJjL2RlZis/==; Path=/; HttpOnly"
            )
        return response

    async def test_full_hosted_login_keeps_csrf_cookie_and_pkce(self):
        auth = ResideoAuth(self.session)
        token = await auth.login("private@example.test", "correct-password", "RO")
        self.assertTrue(self.cookie_verified)
        self.assertEqual(token.access_token, "valid")
        self.assertFalse(hasattr(auth, "password"))
        posts = [call for call in self.calls if call[0] == "POST"]
        self.assertEqual(len(posts), 2)
        self.assertNotIn("client_secret", posts[-1][3].decode())

    async def test_hosted_login_preserves_unquoted_b2c_cookie_values(self):
        self.opaque_b2c_cookies = True
        self.login_redirects = 1
        auth = ResideoAuth(self.session)
        token = await auth.login("private@example.test", "correct-password", "RO")
        self.assertEqual(token.access_token, "valid")
        self.assertIn("stage=complete, reason=none", auth.login_diagnostic())
        token_call = self.calls[-1]
        self.assertTrue(token_call[1].endswith("/token"))
        self.assertNotIn("Cookie", token_call[2])
        self.assertEqual(len([call for call in self.calls if call[0] == "POST"]), 2)

    async def test_bad_password_is_not_retried_or_exposed(self):
        auth = ResideoAuth(self.session)
        with self.assertRaises(AuthenticationError) as error:
            await auth.login("private@example.test", "bad-password")
        self.assertNotIn("private@example.test", str(error.exception))
        self.assertNotIn("bad-password", str(error.exception))
        self.assertEqual(len([x for x in self.calls if x[1].endswith("/SelfAsserted")]), 1)

    async def test_hosted_login_follows_initial_redirects_and_keeps_cookies(self):
        self.login_redirects = 2
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.calls.clear()
                self.login_redirect_status = status
                auth = ResideoAuth(self.session)
                token = await auth.login("private@example.test", "correct-password", "RO")
                self.assertEqual(token.access_token, "valid")
                self.assertTrue(self.cookie_verified)
                self.assertEqual(
                    [x[1] for x in self.calls[:3]],
                    ["/lyricprod.onmicrosoft.com/oauth2/v2.0/authorize", "/signin/1", "/signin/2"],
                )
                self.assertEqual(len([x for x in self.calls if x[0] == "POST"]), 2)
                self.assertNotIn("pre-login", self.calls[-1][2].get("Cookie", ""))

    async def test_hosted_login_rejects_initial_redirect_to_another_origin(self):
        for target in (
            "https://unexpected.example.test/signin",
            self.root.replace("localhost", "127.0.0.1") + "/signin/1",
            self.root.replace("http://", "http://user:secret@") + "/signin/1",
            auth_module.REDIRECT_URI + "?state=unexpected&code=unexpected",
        ):
            with self.subTest(target_shape=urlsplit(target).path):
                self.calls.clear()
                self.login_redirect_target = target
                with self.assertRaises(InvalidResponse):
                    await ResideoAuth(self.session).login(
                        "private@example.test", "correct-password"
                    )
                self.assertEqual(len(self.calls), 1)
                self.assertFalse(any(x[0] == "POST" for x in self.calls))

    async def test_hosted_login_bounds_initial_redirect_loops(self):
        self.login_redirects = 20
        with self.assertRaises(InteractionRequired):
            await ResideoAuth(self.session).login("private@example.test", "correct-password")
        self.assertEqual(len(self.calls), 8)
        self.assertFalse(any(x[0] == "POST" for x in self.calls))

    async def test_interactive_page_after_redirects_still_requires_browser(self):
        self.login_redirects = 2
        self.interactive_page = True
        with self.assertRaises(InteractionRequired):
            await ResideoAuth(self.session).login("private@example.test", "correct-password")
        self.assertEqual(len(self.calls), 3)
        self.assertFalse(any(x[0] == "POST" for x in self.calls))

    async def test_initial_redirect_service_errors_do_not_become_browser_prompts(self):
        self.login_redirects = 1
        for status, error in ((429, RateLimited), (503, CannotConnect)):
            with self.subTest(status=status):
                self.calls.clear()
                self.failures["/signin/1"] = status
                auth = ResideoAuth(self.session)
                with self.assertRaises(error):
                    await auth.login("private@example.test", "correct-password")
                self.assertEqual(len(self.calls), 2)
                self.assertFalse(any(x[0] == "POST" for x in self.calls))

    async def test_login_diagnostic_identifies_each_fallback_without_response_data(self):
        private = "private@example.test private-password private-response-token"
        cases = [
            ({"interactive_page": True}, "authorization_page", "unsupported_login_page"),
            (
                {"credential_reply": "<html>" + private + "</html>"},
                "submit_credentials",
                "credential_response_not_json",
            ),
            (
                {"credential_reply": {"status": "400", "message": "Verify " + private}},
                "submit_credentials",
                "server_requested_interaction",
            ),
            (
                {"confirmation_reply": "<html>" + private + "</html>"},
                "confirm_sign_in",
                "confirmation_not_redirect",
            ),
        ]
        for overrides, stage, reason in cases:
            with self.subTest(stage=stage, reason=reason):
                self.interactive_page = False
                self.credential_reply = self.confirmation_reply = None
                for key, value in overrides.items():
                    setattr(self, key, value)
                auth = ResideoAuth(self.session)
                with self.assertRaises(InteractionRequired):
                    await auth.login("private@example.test", "correct-password")
                diagnostic = auth.login_diagnostic()
                self.assertIn("stage=" + stage, diagnostic)
                self.assertIn("reason=" + reason, diagnostic)
                self.assertIn("http=200", diagnostic)
                for secret in private.split() + ["correct-password", "csrf-test", "one-time-code"]:
                    self.assertNotIn(secret, diagnostic)

    async def test_login_diagnostic_resets_after_a_successful_retry(self):
        auth = ResideoAuth(self.session)
        self.credential_reply = "<html>Unsupported sign-in response</html>"
        with self.assertRaises(InteractionRequired):
            await auth.login("private@example.test", "correct-password")
        self.credential_reply = None
        token = await auth.login("private@example.test", "correct-password")
        self.assertIn("stage=complete, reason=none", auth.login_diagnostic())
        self.assertNotIn(token.refresh_token, auth.login_diagnostic())

    async def test_hosted_login_accepts_browser_normalized_callback_slash(self):
        self.callback_path = "/"
        token = await ResideoAuth(self.session).login("private@example.test", "correct-password")
        self.assertEqual(token.access_token, "valid")
        grant = parse_qs(self.calls[-1][3].decode())
        self.assertEqual(grant["redirect_uri"], [auth_module.REDIRECT_URI])

    async def test_browser_callback_accepts_both_paths_and_preserves_pkce(self):
        for path in ("", "/"):
            with self.subTest(path=path):
                authorization = ResideoAuth.new_authorization()
                query = parse_qs(urlsplit(authorization["url"]).query)
                self.auth_codes["challenge"] = query["code_challenge"][0]
                callback = (
                    auth_module.REDIRECT_URI
                    + path
                    + "?"
                    + urlencode(
                        {"state": authorization["state"], "code": "opaque-code+with/symbols_-."}
                    )
                )
                token = await self.auth.exchange_callback(callback, authorization)
                self.assertEqual(token.access_token, "valid")
                grant = parse_qs(self.calls[-1][3].decode())
                self.assertEqual(grant["code"], ["opaque-code+with/symbols_-."])
                self.assertEqual(grant["code_verifier"], [authorization["verifier"]])
                self.assertEqual(grant["redirect_uri"], [auth_module.REDIRECT_URI])

    async def test_browser_callback_requires_matching_state_and_redirect(self):
        authorization = ResideoAuth.new_authorization()
        query = "?" + urlencode({"code": "synthetic-code", "state": authorization["state"]})
        for callback in [
            auth_module.REDIRECT_URI + "?code=stolen&state=wrong",
            "https://evil.test?code=x&state=x",
            auth_module.REDIRECT_URI + "/unexpected" + query,
            auth_module.REDIRECT_URI + "//" + query,
            auth_module.REDIRECT_URI + query + "#unexpected",
            auth_module.REDIRECT_URI + query + "&state=",
            auth_module.REDIRECT_URI + query + "&code=",
            auth_module.REDIRECT_URI + "?code=x&state=\u021b",
            "https://[",
        ]:
            with (
                self.subTest(callback_shape=callback.split("?")[0]),
                self.assertRaises(AuthenticationError),
            ):
                await self.auth.exchange_callback(callback, authorization)
        self.assertFalse(self.calls)

    async def test_browser_callback_with_wrong_verifier_is_rejected(self):
        authorization = ResideoAuth.new_authorization()
        self.auth_codes["challenge"] = "different-challenge"
        callback = (
            auth_module.REDIRECT_URI
            + "/?"
            + urlencode({"state": authorization["state"], "code": "synthetic-code"})
        )
        with self.assertRaises(AuthenticationError):
            await self.auth.exchange_callback(callback, authorization)
        self.assertEqual(len(self.calls), 1)

    async def test_current_b2c_settings_and_malicious_settings(self):
        good = {
            "hosts": {
                "tenant": "/lyricprod.onmicrosoft.com/B2C_1A_SignIn_Mob_HH",
                "policy": "B2C_1A_SignIn_Mob_HH",
            },
            "csrf": "x",
            "transId": "x",
            "api": "CombinedSigninAndSignup",
        }
        self.assertEqual(ResideoAuth.read_settings("var SETTINGS = " + json.dumps(good)), good)
        good["hosts"]["tenant"] = "//evil.test"
        with self.assertRaises(InteractionRequired):
            ResideoAuth.read_settings("var SETTINGS = " + json.dumps(good))

    async def test_session_then_discovery_and_units(self):
        devices = await self.client.update()
        self.assertEqual(list(devices), ["T6-test"])
        self.assertEqual(devices["T6-test"].unit, "Celsius")
        self.assertEqual(devices["T6-test"].current_temperature, 21)
        self.assertEqual(devices["T6-test"].temperature_limits("heat"), (5, 35))
        self.assertIsNone(devices["T6-test"].humidity)
        self.assertEqual(self.client.account_id, "456")
        self.assertEqual([x[1] for x in self.calls], ["/api/v2/session", "/api/v4/locations"])
        self.assertEqual(self.calls[-1][2]["AppVer"], "6.21.1")
        self.assertEqual(
            self.calls[-1][2]["Ocp-Apim-Subscription-Key"], "8c9485374bab4b1aa4b3555ac2f032c4"
        )

    async def test_concurrent_expired_tokens_refresh_only_once(self):
        changes = []
        self.auth.on_token = changes.append
        self.auth.token.expires_at = 0
        tokens = await asyncio.gather(*(self.auth.access_token() for _ in range(8)))
        self.assertEqual(tokens, ["valid"] * 8)
        self.assertEqual(self.refresh_count, 1)
        self.assertEqual(changes[0].refresh_token, "rotated-1")

    async def test_http_401_refreshes_once_then_retries(self):
        self.auth.token.access_token = "expired"
        await self.client.update()
        self.assertEqual(self.refresh_count, 1)
        self.assertEqual(len([x for x in self.calls if x[1] == "/api/v2/session"]), 2)

    async def test_permanent_401_does_not_loop(self):
        self.failures["/api/v2/session"] = 401
        with self.assertRaises(AuthenticationError):
            await self.client.update()
        self.assertEqual(self.refresh_count, 1)
        self.assertEqual(len([x for x in self.calls if x[1] == "/api/v2/session"]), 2)

    async def test_429_prevents_repeated_requests(self):
        self.failures["/api/v2/session"] = 429
        for _ in range(3):
            with self.assertRaises(RateLimited):
                await self.client.update()
        self.assertEqual(len(self.calls), 1)

    async def test_invalid_locations_does_not_become_successful_empty_account(self):
        self.payload = {"unexpected": "shape"}
        with self.assertRaises(InvalidResponse):
            await self.client.update()

    async def test_setpoint_mode_and_schedule_match_apk_routes(self):
        await self.client.update()
        await self.client.set_temperature("T6-test", heat=22.5)
        method, path, _, data = self.calls[-1]
        self.assertEqual(
            (method, path), ("PUT", "/api/v2/locations/123/devices/T6-test/thermostat/HeatSetpoint")
        )
        self.assertEqual(
            json.loads(data),
            {
                "thermostatSetpoint": 72.5,
                "thermostatSetpointStatus": "TemporaryHold",
                "unit": "Celsius",
            },
        )
        await self.client.set_mode("T6-test", "Off")
        self.assertEqual(json.loads(self.calls[-1][3]), {"thermostatMode": "Off"})
        self.assertEqual(self.calls[-1][1], "/api/locations/123/devices/T6-test/thermostat/Mode")
        await self.client.set_hold("T6-test", "NoHold")
        self.assertEqual(json.loads(self.calls[-1][3]), {"Status": "NoHold"})

    async def test_invalid_and_unsupported_commands_never_reach_network(self):
        await self.client.update()
        baseline = len(self.calls)
        for value in [float("nan"), float("inf"), -100, 100, True, "bad"]:
            with self.assertRaises(CommandError):
                await self.client.set_temperature("T6-test", heat=value)
        with self.assertRaises(CommandError):
            await self.client.set_temperature("T6-test", cool=20)
        with self.assertRaises(CommandError):
            await self.client.set_mode("T6-test", "Cool")
        self.client.devices["T6-test"].raw["thermostat"]["units"] = "Unknown"
        with self.assertRaises(CommandError):
            await self.client.set_temperature("T6-test", heat=22)
        self.assertEqual(len(self.calls), baseline)

    async def test_auto_mode_sends_both_values_atomically(self):
        raw = self.payload[0]["devices"][1]["thermostat"]
        raw.update(
            {
                "allowedModes": ["Heat", "Cool", "Auto", "Off"],
                "minCoolSetpoint": 60.8,
                "maxCoolSetpoint": 95,
                "deadband": 2,
            }
        )
        raw["changeableValues"]["autoChangeoverActive"] = True
        await self.client.update()
        with self.assertRaises(CommandError):
            await self.client.set_temperature("T6-test", heat=22, cool=23)
        await self.client.set_temperature("T6-test", heat=20, cool=24)
        method, path, _, body = self.calls[-1]
        self.assertEqual(
            (method, path),
            ("POST", "/api/locations/123/devices/T6-test/thermostat/changeableValues"),
        )
        data = json.loads(body)
        self.assertEqual(
            (data["heatSetPoint"], data["coolSetPoint"], data["unit"]), (68, 75.2, "Celsius")
        )

    async def test_reported_jasper_values_and_celsius_command_round_trip(self):
        raw = self.payload[0]["devices"][1]["thermostat"]
        raw["indoorTemperature"] = 78.8
        raw["changeableValues"]["heatSetpoint"] = 73.4
        await self.client.update()
        device = self.client.devices["T6-test"]
        self.assertEqual(device.current_temperature, 26)
        self.assertEqual(device.setpoint("heat"), 23)
        self.assertEqual(device.temperature_limits("heat"), (5, 35))
        await self.client.set_temperature("T6-test", heat=23)
        self.assertEqual(
            json.loads(self.calls[-1][3]),
            {
                "thermostatSetpoint": 73.4,
                "thermostatSetpointStatus": "TemporaryHold",
                "unit": "Celsius",
            },
        )
        # Read conversion must not mutate or progressively reconvert API data.
        self.assertEqual(device.thermostat["indoorTemperature"], 78.8)
        self.assertEqual(device.current_temperature, 26)

    async def test_fahrenheit_preference_is_not_converted_twice(self):
        raw = self.payload[0]["devices"][1]["thermostat"]
        raw["units"] = "Fahrenheit"
        raw["indoorTemperature"] = 78.8
        raw["changeableValues"]["heatSetpoint"] = 73.4
        await self.client.update()
        device = self.client.devices["T6-test"]
        self.assertEqual(device.current_temperature, 78.8)
        self.assertEqual(device.setpoint("heat"), 73.4)
        self.assertEqual(device.temperature_limits("heat"), (41, 95))
        await self.client.set_temperature("T6-test", heat=74)
        data = json.loads(self.calls[-1][3])
        self.assertEqual((data["thermostatSetpoint"], data["unit"]), (74, "Fahrenheit"))

    async def test_native_celsius_model_is_not_converted(self):
        raw = self.payload[0]["devices"][1]
        raw["deviceType"] = raw["deviceModel"] = "HoneyBadger"
        raw["thermostat"].update(
            {"indoorTemperature": 26, "minHeatSetpoint": 5, "maxHeatSetpoint": 35}
        )
        raw["thermostat"]["changeableValues"]["heatSetpoint"] = 23
        await self.client.update()
        device = self.client.devices["T6-test"]
        self.assertEqual(device.current_temperature, 26)
        self.assertEqual(device.setpoint("heat"), 23)
        self.assertEqual(device.temperature_limits("heat"), (5, 35))
        await self.client.set_temperature("T6-test", heat=23)
        self.assertEqual(json.loads(self.calls[-1][3])["thermostatSetpoint"], 23)

    async def test_jasper_model_fallback_and_temperature_boundaries(self):
        raw = self.payload[0]["devices"][1]
        del raw["deviceType"]
        raw["deviceModel"] = "Jasper"
        await self.client.update()
        self.assertEqual(self.client.devices["T6-test"].temperature_limits("heat"), (5, 35))
        for value, wire in ((5, 41), (35, 95), (22.5, 72.5)):
            await self.client.set_temperature("T6-test", heat=value)
            self.assertEqual(json.loads(self.calls[-1][3])["thermostatSetpoint"], wire)
        baseline = len(self.calls)
        for value in (4.5, 35.5, 73.4):
            with self.assertRaises(CommandError):
                await self.client.set_temperature("T6-test", heat=value)
        self.assertEqual(len(self.calls), baseline)

    async def test_auto_deadband_is_checked_in_preferred_units(self):
        raw = self.payload[0]["devices"][1]["thermostat"]
        raw.update(
            {
                "allowedModes": ["Heat", "Cool", "Auto", "Off"],
                "minCoolSetpoint": 60.8,
                "maxCoolSetpoint": 95,
                "deadband": 2,
            }
        )
        raw["changeableValues"]["autoChangeoverActive"] = True
        await self.client.update()
        baseline = len(self.calls)
        with self.assertRaises(CommandError):
            await self.client.set_temperature("T6-test", heat=22, cool=23.5)
        self.assertEqual(len(self.calls), baseline)
        await self.client.set_temperature("T6-test", heat=22, cool=24)
        data = json.loads(self.calls[-1][3])
        self.assertEqual((data["heatSetPoint"], data["coolSetPoint"]), (71.6, 75.2))

    async def test_offline_and_missing_limits_prevent_writes(self):
        await self.client.update()
        baseline = len(self.calls)
        self.client.devices["T6-test"].raw["isAlive"] = False
        with self.assertRaises(CommandError):
            await self.client.set_mode("T6-test", "Heat")
        self.client.devices["T6-test"].raw["isAlive"] = True
        del self.client.devices["T6-test"].raw["thermostat"]["maxHeatSetpoint"]
        with self.assertRaises(CommandError):
            await self.client.set_temperature("T6-test", heat=22)
        self.assertEqual(len(self.calls), baseline)

    async def test_parser_ignores_titan_and_other_products(self):
        payload = deepcopy(locations())
        payload[0]["devices"].append(
            {"deviceClass": "Thermostat", "deviceID": "Titan", "status": {}}
        )
        self.assertEqual(list(parse_locations(payload)), ["T6-test"])


if __name__ == "__main__":
    unittest.main()
