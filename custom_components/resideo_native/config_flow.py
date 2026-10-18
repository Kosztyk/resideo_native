"""Account, browser PKCE, and advanced refresh-token setup."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_COUNTRY,
    CONF_DEFAULT_HOLD,
    CONF_POLL_INTERVAL,
    CONF_TOKEN,
    DEFAULT_HOLD,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    NAME,
)
from .protocol import (
    AuthenticationError,
    CannotConnect,
    InteractionRequired,
    InvalidCallback,
    NativeClient,
    RateLimited,
    ResideoAuth,
    ResideoError,
)

PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


class ResideoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._authorization: dict[str, str] | None = None
        self._sign_in_country: str | None = None
        self._browser_required = False

    def _country(self) -> str:
        if self._sign_in_country:
            return self._sign_in_country
        country = self.hass.config.country
        if self.source == config_entries.SOURCE_REAUTH:
            country = self._get_reauth_entry().data.get(CONF_COUNTRY, country)
        return country.upper() if country and len(country) == 2 else "RO"

    @callback
    def _error(self, err: ResideoError) -> str:
        if isinstance(err, InteractionRequired):
            return "interaction_required"
        if isinstance(err, InvalidCallback):
            return "invalid_callback"
        if isinstance(err, AuthenticationError):
            return "invalid_auth"
        if isinstance(err, RateLimited):
            return "rate_limited"
        if isinstance(err, CannotConnect):
            return "cannot_connect"
        return "unexpected_response"

    async def _finish(self, auth: ResideoAuth, country: str):
        client = NativeClient(async_get_clientsession(self.hass), auth)
        devices = await client.update()
        if not devices:
            return self.async_abort(reason="no_thermostats")
        await self.async_set_unique_id(client.account_id)
        data = {CONF_TOKEN: auth.token.as_dict(), CONF_COUNTRY: country}
        if self.source == config_entries.SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=data)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=NAME, data=data)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        return self.async_show_menu(
            step_id="user", menu_options=["account", "browser", "refresh_token"]
        )

    async def async_step_account(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input:
            auth = ResideoAuth(async_get_clientsession(self.hass))
            country = user_input[CONF_COUNTRY].strip().upper()
            self._sign_in_country = country
            try:
                await auth.login(
                    user_input[CONF_USERNAME].strip(), user_input[CONF_PASSWORD], country
                )
                return await self._finish(auth, country)
            except InteractionRequired:
                self._browser_required = True
                return await self.async_step_browser()
            except ResideoError as err:
                errors["base"] = self._error(err)
        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
                ),
                vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
                vol.Required(CONF_COUNTRY, default=self._country()): vol.All(
                    str, vol.Match(r"^[A-Za-z]{2}$")
                ),
            }
        )
        return self.async_show_form(step_id="account", data_schema=schema, errors=errors)

    async def async_step_browser(self, user_input: dict[str, Any] | None = None):
        errors = {"base": "interaction_required"} if self._browser_required else {}
        self._browser_required = False
        country = self._country()
        if self._authorization is None:
            self._authorization = ResideoAuth.new_authorization(country)
        if user_input:
            auth = ResideoAuth(async_get_clientsession(self.hass))
            try:
                await auth.exchange_callback(user_input["redirect_url"], self._authorization)
                return await self._finish(auth, country)
            except InvalidCallback as err:
                # Validation failed locally; the code has not been exchanged.
                errors["base"] = self._error(err)
            except ResideoError as err:
                errors["base"] = self._error(err)
                # Authorization codes are one-time. Generate a fresh link.
                self._authorization = ResideoAuth.new_authorization(country)
        return self.async_show_form(
            step_id="browser",
            data_schema=vol.Schema({vol.Required("redirect_url"): PASSWORD_SELECTOR}),
            errors=errors,
            description_placeholders={"login_url": self._authorization["url"]},
        )

    async def async_step_refresh_token(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input:
            auth = ResideoAuth(async_get_clientsession(self.hass))
            try:
                await auth.import_refresh_token(user_input["refresh_token"])
                return await self._finish(auth, self._country())
            except ResideoError as err:
                errors["base"] = self._error(err)
        return self.async_show_form(
            step_id="refresh_token",
            data_schema=vol.Schema({vol.Required("refresh_token"): PASSWORD_SELECTOR}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return ResideoOptionsFlow()


class ResideoOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=30, max=600)),
                    vol.Required(
                        CONF_DEFAULT_HOLD,
                        default=self.config_entry.options.get(CONF_DEFAULT_HOLD, DEFAULT_HOLD),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value="TemporaryHold", label="Until the next scheduled period"
                                ),
                                selector.SelectOptionDict(
                                    value="PermanentHold", label="Permanent hold"
                                ),
                            ]
                        )
                    ),
                }
            ),
        )
