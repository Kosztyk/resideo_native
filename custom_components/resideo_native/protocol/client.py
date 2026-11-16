"""Asynchronous legacy Resideo / Honeywell Home mobile API client.

Only routes and command bodies recovered from the supplied Android app are used.
GET session initializes the account before discovery; account changes, phone geofence registration,
push registrations, and firmware operations are deliberately outside this client.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
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
from .rooms import (
    ROOM_PRIORITY_HOLDS,
    discover_group_ids,
    parse_room_priority,
    parse_room_response,
)
from .priority_validation import priority_error_evidence
from .schedules import ScheduleClientMixin
from .schedule_modes import ScheduleModesMixin
from .validation_error import schedule_validation_detail

_LOGGER = logging.getLogger(__name__)
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
        self._rooms_error_types: dict[str, str] = {}
        self._room_retry_after: dict[str, float] = {}

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
        devices = parse_locations(await self._request("GET", "api/v4/locations"))
        # Fetch only FlyCatcher-family room accessories. Optional room API
        # failures cannot take working climate entities offline.
        for device in devices.values():
            if device.supports_rooms and device.online:
                await self._update_flycatcher_rooms(device)
        self.devices = devices
        return devices

    async def _update_flycatcher_rooms(self, device: Thermostat) -> None:
        """Read the Android app's group/rooms API, with priority fallback.

        The API is observed in Android 6.21.2. No pairing, priority, or
        configuration writes are made. Avoid logging cloud body or IDs.
        """
        if time.monotonic() < self._room_retry_after.get(device.device_id, 0):
            return
        combined = {}
        failures = []
        group_ids = discover_group_ids(device.raw)
        for group_id in group_ids:
            path = self._path(device, f"group/{group_id}/rooms", "v1/")
            try:
                async with asyncio.timeout(12):
                    payload = await self._request("GET", path)
                combined.update(parse_room_response(
                    payload, group_id=group_id,
                    convert_temperature=device._temperature_from_wire,
                ))
            except (AuthenticationError, CannotConnect, InteractionRequired,
                    InvalidResponse, RateLimited, TimeoutError) as err:
                failures.append(type(err).__name__)
        # The same APK provides /priority; read it for the room-priority
        # selector and as a fallback source of per-room values. This does not
        # alter device settings.
        path = self._path(device, "priority", "v1/")
        try:
            async with asyncio.timeout(12):
                priority = await self._request("GET", path)
            device.room_priority = parse_room_priority(priority)
            if not combined:
                combined.update(parse_room_response(
                    priority, group_id=group_ids[0],
                    convert_temperature=device._temperature_from_wire,
                ))
        except (AuthenticationError, CannotConnect, InteractionRequired,
                InvalidResponse, RateLimited, TimeoutError) as err:
            failures.append(type(err).__name__)
        device.room_accessories = combined
        if failures and not combined:
            self._room_retry_after[device.device_id] = time.monotonic() + 900
        else:
            self._room_retry_after.pop(device.device_id, None)
        # Emit once per failure-category transition; avoid flooding the log
        # every 60 seconds on devices lacking the optional endpoint.
        new_error = ",".join(sorted(set(failures))) if failures and not combined else ""
        old_error = self._rooms_error_types.get(device.device_id, "")
        if new_error != old_error:
            if new_error:
                _LOGGER.warning(
                    "FlyCatcher room discovery unavailable; the thermostat remains available "
                    "(error_classes=%s, group_count=%d)", new_error, len(group_ids),
                )
            elif old_error:
                _LOGGER.info("FlyCatcher room discovery recovered")
            self._rooms_error_types[device.device_id] = new_error

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
                            # Priority 400: preserve only finite allowlisted hints. Never
                            # expose server-controlled message text or codes to HA/logs.
                            if method == "PUT" and path.endswith("/priority") and response.status in (400, 422):
                                fmt, reason, field = priority_error_evidence(text)
                                err = CommandError(message)
                                err.priority_response_format = fmt
                                err.priority_validation_reason = reason
                                err.priority_validation_field = field
                                raise err
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

    async def set_room_priority(
        self, device_id: str, priority_type: str, selected_rooms: list[int],
    ) -> None:
        """Send one validated FlyCatcher priority write, never auto-retry.

        "All rooms" is a PickARoom command with every reported room ID.
        The standalone WholeHouse legacy command returned HTTP 400 and is
        deliberately unavailable. The FollowMe write follows APK 6.21.2
        Gson SerializedName annotations: SetPriorityRequest.priority is
        "currentPriority" and Priority.type is "priorityType". The app's
        null selectedRooms value is omitted by its default Gson serializer.
        A manual change while following the schedule uses a temporary hold.
        """
        if priority_type not in ("FollowMe", "PickARoom"):
            raise CommandError("Unsupported priority write; use PickARoom for All rooms")
        if (not isinstance(selected_rooms, list)
                or any(type(r) is not int for r in selected_rooms)
                or len(set(selected_rooms)) != len(selected_rooms)):
            raise CommandError("Room selection must contain distinct room IDs")
        async with self._command_lock:
            device = self._device(device_id)
            if not device.supports_rooms or device.room_priority is None:
                raise CommandError("FlyCatcher room priority has not been discovered")
            valid_ids = {rid for rid, _ in device.room_priority.room_names}
            if priority_type == "PickARoom":
                if not selected_rooms or any(r not in valid_ids for r in selected_rooms):
                    raise CommandError("Choose one or more rooms reported by the thermostat")
                # This exact body has been verified with real FlyCatcher
                # single-room and multi-room selections. Do not alter it.
                shape = "currentPriority_pick"
                status_label = status_origin = "none"
                body: dict[str, Any] = {
                    "currentPriority": {
                        "priorityType": "PickARoom",
                        "selectedRooms": sorted(selected_rooms),
                    }
                }
            else:
                if selected_rooms:
                    raise CommandError("Follow Me does not accept a room selection")
                # Android 6.21.2 DEX: Ly9/u.F constructs SetPriorityRequest.
                # Gson @SerializedName on SetPriorityRequest.priority is
                # "currentPriority"; Priority.type is "priorityType".
                # Loa/d.c returns null for FollowMe and the app constructs
                # a default Gson, which omits null object fields. So omit
                # selectedRooms; don't send the old "priority" / "type" keys.
                shape = "currentPriority_follow_me"
                status = device.room_priority.hold_status
                status_origin = "priority_get"
                thermostat_status = device.values.get("thermostatSetpointStatus")
                if status is None or (
                    status == "NoHold" and thermostat_status in ROOM_PRIORITY_HOLDS
                ):
                    status = thermostat_status
                    status_origin = "thermostat_fallback"
                if status == "NoHold" and device.schedule_enabled is not False:
                    # The running schedule can immediately restore its own room priority.
                    status = "TemporaryHold"
                    status_origin = "schedule_override"
                if status not in ("NoHold", *ROOM_PRIORITY_HOLDS):
                    raise CommandError(
                        "Resideo priority hold status is unknown; Follow Me was not sent"
                    )
                status_label = status
                body = {
                    "currentPriority": {"priorityType": "FollowMe"},
                    "status": status,
                }
                if status == "HoldUntil":
                    until = device.room_priority.hold_until
                    if status_origin == "thermostat_fallback" or not until:
                        until = device.values.get("holdUntil") or until
                    if not isinstance(until, str) or not until.strip():
                        raise CommandError(
                            "HoldUntil expiration is unknown; Follow Me was not sent"
                        )
                    body["holdUntil"] = until
            try:
                await self._request(
                    "PUT", self._path(device, "priority", "v1/"), body,
                )
            except (CommandError, CannotConnect, RateLimited, AuthenticationError,
                    InteractionRequired) as err:
                # Never log server response text, request bodies, secret IDs,
                # authentication data or room names.
                match = re.search(r"HTTP (\d{3})", str(err)) if isinstance(err, CommandError) else None
                _LOGGER.warning(
                    "FlyCatcher room priority write failed "
                    "(mode=%s, room_count=%d, http=%s, category=%s, "
                    "request_shape=%s, hold_status=%s, status_source=%s, "
                    "response_format=%s, validation_hint=%s, field_hint=%s)",
                    priority_type, len(selected_rooms),
                    match.group(1) if match else "none", type(err).__name__,
                    shape, status_label, status_origin,
                    getattr(err, "priority_response_format", "unknown"),
                    getattr(err, "priority_validation_reason", "unknown"),
                    getattr(err, "priority_validation_field", "none"),
                )
                raise
            _LOGGER.debug(
                "FlyCatcher room priority request accepted "
                "(mode=%s, hold_status=%s, status_source=%s)",
                priority_type, status_label, status_origin,
            )

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
