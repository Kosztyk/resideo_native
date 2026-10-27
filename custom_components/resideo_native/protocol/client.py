"""Asynchronous legacy Resideo / Honeywell Home mobile API client.

Only routes and command bodies recovered from the supplied Android app are used.
GET session initializes the account before discovery; account changes, phone geofence registration,
push registrations, and firmware operations are deliberately outside this client.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import aiohttp

from .auth import TIMEOUT, USER_AGENT, ResideoAuth, retry_seconds
from .device import Thermostat, number, parse_locations
from .errors import (
    AuthenticationError,
    CannotConnect,
    CommandError,
    InteractionRequired,
    InvalidResponse,
    RateLimited,
)
from .hot_water import DHW_BOOST_MINUTES
from .schedules import ScheduleClientMixin
from .schedule_modes import ScheduleModesMixin
from .validation_error import schedule_validation_detail

BASE_URL = "https://lyric.alarmnet.com/"
# Public subscription identifier shipped with the Resideo app; not a user's key.
APP_SUBSCRIPTION = "8c9485374bab4b1aa4b3555ac2f032c4"


class NativeClient(ScheduleClientMixin, ScheduleModesMixin):
    def __init__(self, session: aiohttp.ClientSession, auth: ResideoAuth) -> None:
        self.session = session
        self.auth = auth
        self.account_id: str | None = None
        self.username: str | None = None
        self.devices: dict[str, Thermostat] = {}
        self._initialized = False
        self._session_lock = asyncio.Lock()
        self._command_lock = asyncio.Lock()
        self._retry_at = 0.0

    async def initialize(self) -> None:
        async with self._session_lock:
            if self._initialized:
                return
            data = await self._request("GET", "api/v2/session")
            user = data.get("user") if isinstance(data, dict) else None
            if not isinstance(user, dict) or user.get("userID") is None:
                raise InvalidResponse("Resideo did not return the expected legacy account session")
            self.account_id = str(user["userID"])
            self.username = user.get("username")
            self._initialized = True

    async def update(self) -> dict[str, Thermostat]:
        await self.initialize()
        self.devices = parse_locations(await self._request("GET", "api/v4/locations"))
        return self.devices

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if self._retry_at > time.monotonic():
            raise RateLimited(self._retry_at - time.monotonic())
        for attempt in range(2):
            token = await self.auth.access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Ocp-Apim-Subscription-Key": APP_SUBSCRIPTION,
                "ActivityId": str(uuid4()),
                "AppVer": "6.21.1",
                "User-Agent": USER_AGENT,
                "MobileClientTime": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
            }
            try:
                async with self.session.request(
                    method,
                    BASE_URL + path,
                    headers=headers,
                    json=body,
                    timeout=TIMEOUT,
                    allow_redirects=False,
                ) as response:
                    if response.status == 401:
                        if attempt:
                            raise AuthenticationError("Resideo rejected the renewed authorization")
                        await self.auth.access_token(rejected_token=token)
                        continue
                    if response.status == 429:
                        pause = retry_seconds(response.headers.get("Retry-After"))
                        self._retry_at = time.monotonic() + pause
                        raise RateLimited(pause)
                    text = await response.text()
                    if response.status == 403:
                        # Terms must be accepted by the user in the official app.
                        raise InteractionRequired(
                            "Resideo denied access; check sign-in and pending terms in the app"
                        )
                    if response.status >= 500:
                        raise CannotConnect("Resideo API is temporarily unavailable")
                    if not 200 <= response.status < 300:
                        if method != "GET":
                            message = f"Resideo rejected the command (HTTP {response.status})"
                            if path.endswith(("/ThermostatSchedule", "/dhw/schedule", "/Schedule/Status")):
                                secrets = [token, self.account_id, self.username]
                                for device in self.devices.values():
                                    secrets.extend([device.device_id, device.location_id, device.name])
                                message += ": " + schedule_validation_detail(text, secrets)
                            raise CommandError(message)
                        raise InvalidResponse(f"Resideo API returned HTTP {response.status}")
                    if not text.strip():
                        if method == "GET":
                            raise InvalidResponse("Resideo returned an empty API response")
                        return None
                    try:
                        return json.loads(text)
                    except ValueError as err:
                        raise InvalidResponse("Resideo returned an invalid JSON response") from err
            except (TimeoutError, aiohttp.ClientError) as err:
                # A timed-out write may already have executed. Never replay it.
                message = "Cannot reach Resideo"
                if method != "GET":
                    message += "; command delivery may be unknown"
                raise CannotConnect(message) from err
        raise AuthenticationError("Sign in to Resideo again")

    def _device(self, device_id: str) -> Thermostat:
        device = self.devices.get(device_id)
        if device is None:
            raise CommandError("The thermostat is no longer in this Resideo account")
        if not device.online:
            raise CommandError("The thermostat is offline")
        return device

    @staticmethod
    def _path(device: Thermostat, suffix: str, version: str = "") -> str:
        return f"api/{version}locations/{quote(device.location_id, safe='')}/devices/{quote(device.device_id, safe='')}/{suffix}"

    async def set_mode(self, device_id: str, mode: str) -> None:
        async with self._command_lock:
            device = self._device(device_id)
            if mode not in device.allowed_modes:
                raise CommandError("This operating mode is not supported by the thermostat")
            await self._request(
                "PUT", self._path(device, "thermostat/Mode"), {"thermostatMode": mode}
            )

    async def set_temperature(
        self,
        device_id: str,
        *,
        heat: float | None = None,
        cool: float | None = None,
        hold: str = "TemporaryHold",
    ) -> None:
        async with self._command_lock:
            device = self._device(device_id)
            if hold not in ("TemporaryHold", "PermanentHold"):
                raise CommandError("Unsupported temperature hold type")
            if heat is None and cool is None:
                raise CommandError("A temperature is required")
            if heat is not None:
                heat = device.validate_temperature(heat, "heat")
                if not any(mode in device.allowed_modes for mode in ("Heat", "Auto", "AutoHeat")):
                    raise CommandError("The thermostat does not support heating")
            if cool is not None:
                cool = device.validate_temperature(cool, "cool")
                if not any(mode in device.allowed_modes for mode in ("Cool", "Auto", "AutoCool")):
                    raise CommandError("The thermostat does not support cooling")
            if device.mode == "Auto" and (heat is None or cool is None):
                raise CommandError("Both temperature limits are required in automatic mode")
            if heat is not None and cool is not None:
                if device.mode != "Auto" or "Auto" not in device.allowed_modes:
                    raise CommandError(
                        "A temperature range requires automatic heating/cooling mode"
                    )
                gap = number(device.thermostat.get("deadband"))
                if gap is None or gap < 0:
                    raise CommandError("Resideo did not report a valid heating/cooling deadband")
                if heat >= cool or cool - heat < gap:
                    raise CommandError(
                        "Heating and cooling limits violate the thermostat's deadband"
                    )
                body = {
                    "autoChangeoverActive": True,
                    "heatSetPoint": device.temperature_to_wire(heat),
                    "coolSetPoint": device.temperature_to_wire(cool),
                    "mode": "Auto",
                    "thermostatSetpointStatus": hold,
                    "unit": device.unit,
                }
                await self._request("POST", self._path(device, "thermostat/changeableValues"), body)
                return
            body = {
                "thermostatSetpoint": device.temperature_to_wire(
                    heat if heat is not None else cool
                ),
                "thermostatSetpointStatus": hold,
                "unit": device.unit,
            }
            suffix = "thermostat/HeatSetpoint" if heat is not None else "thermostat/Coolsetpoint"
            await self._request("PUT", self._path(device, suffix, "v2/"), body)

    async def set_hold(self, device_id: str, status: str) -> None:
        async with self._command_lock:
            if status not in ("NoHold", "PermanentHold", "TemporaryHold"):
                raise CommandError("Unsupported hold status")
            device = self._device(device_id)
            body = {"Status": status}
            next_period = device.values.get("nextPeriodTime")
            if status == "TemporaryHold" and isinstance(next_period, str) and next_period:
                body["HoldUntil"] = next_period
            await self._request("PUT", self._path(device, "hold"), body)

    def _hot_water_device(self, device_id: str) -> Thermostat:
        device = self._device(device_id)
        zone = device.hot_water
        if zone is None:
            raise CommandError("This thermostat has no hot-water zone")
        if not zone.online:
            raise CommandError("The hot-water zone is offline")
        if not zone.can_control:
            raise CommandError("Hot-water control is supported only for legacy Jasper thermostats")
        return device

    async def set_hot_water_mode(self, device_id: str, mode: str) -> None:
        """Use the app's permanent switch or resume-schedule command.

        The path uses the PARENT thermostat ID, not dhwZone.deviceId.
        APK 6.21.1: Ce/c.Q0, Ce/c.m, ta/h.N3 and ta/h.onActivityResult.
        """
        async with self._command_lock:
            if mode not in ("auto", "on", "off"):
                raise CommandError("Unsupported hot-water operating mode")
            device = self._hot_water_device(device_id)
            if mode == "auto":
                suffix, body = "dhw/scheduleStatus", {"scheduleStatus": "Resume"}
            else:
                suffix = "dhw/systemSwitch"
                body = {"systemSwitch": "Heat" if mode == "on" else "Off"}
            await self._request("PUT", self._path(device, suffix, "v3/"), body)

    async def boost_hot_water(self, device_id: str, duration: int = 30) -> None:
        """Start a timed boost; minutes are encoded as boostTime, not boostDuration."""
        async with self._command_lock:
            if type(duration) is not int or duration not in DHW_BOOST_MINUTES:
                raise CommandError("Hot-water boost duration must be 30, 60 or 90 minutes")
            device = self._hot_water_device(device_id)
            await self._request(
                "PUT", self._path(device, "dhw/state", "v3/"),
                {"dhwState": "On", "boostTime": duration},
            )

    async def cancel_hot_water_boost(self, device_id: str) -> None:
        """Send the app's turnHotWaterOff request, distinct from permanent off."""
        async with self._command_lock:
            device = self._hot_water_device(device_id)
            await self._request(
                "PUT", self._path(device, "dhw/state", "v3/"), {"dhwState": "Off"}
            )
