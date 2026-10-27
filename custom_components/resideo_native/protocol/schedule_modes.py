"""Per-thermostat Timed/Geofence selection and native schedule On/Off."""

from urllib.parse import quote

from .device import parse_locations
from .errors import CommandError, ResideoError
from .schedule_rules import DAYS, geofence_profile, geofence_settings, sleep_readback_matches
from .schedules import present, revision, timed_body
from .schedule_readback import verification_result, verify_readback


def _check_revision(raw, expected):
    if not isinstance(expected, str) or expected != revision(raw):
        raise CommandError("Schedule changed or revision is missing; fetch it again before saving")



class ScheduleModesMixin:
    async def set_schedule_mode(self, device_id, mode, expected_revision, *, confirm_change=False, days=None, geofence=None):
        device = self._schedule_device(device_id, False)
        async with self._command_lock:
            raw = await self._read_schedule(device, False)
            try:
                _check_revision(raw, expected_revision)
                if mode not in ("Timed", "Geofence"):
                    raise CommandError("Choose Timed or Geofence; use the schedule On/Off switch to enable or disable it")
                if confirm_change is not True:
                    raise CommandError("Confirm the schedule type change before saving")
                if raw.get("scheduleType") not in ("Timed", "Geofence", "None") or raw.get("scheduleSubType") not in ("EMEA", "None", None):
                    raise CommandError("Only EMEA heating schedules support these controls")
                if mode == "Timed":
                    if geofence is not None:
                        raise CommandError("Geofence temperatures do not belong to a Timed request")
                    if days is None:
                        stored = present(raw, device, False)["days"]
                        if not any(stored.values()):
                            raise CommandError("No stored timed periods returned; enter your routine or import a backup")
                        days = {d: stored.get(d, []) for d in DAYS}
                    if not isinstance(days, dict) or set(days) != set(DAYS):
                        raise CommandError("Switching to Timed requires all seven day lists; empty days are allowed")
                    body = timed_body(raw, days, device)
                else:
                    if days is not None:
                        raise CommandError("Timed days do not belong to a Geofence request")
                    settings = geofence_settings(raw, device, geofence)
                    body = {"scheduleType": "Geofence", "deviceIDs": [device_id], "geoFenceSchedule": settings}
            except CommandError as err:
                raise CommandError(f"{err}; no write was sent") from err
            path = f"api/v3/locations/{quote(device.location_id, safe='')}/ThermostatSchedule"
            await self._request("PUT", path, body)
            if mode == "Timed":
                return await self._verify_written_schedule(device, body, False)
            def matches(result):
                return (
                    result.get("scheduleType") == "Geofence"
                    and geofence_profile(body, device) == geofence_profile(result, device)
                    and sleep_readback_matches(body["geoFenceSchedule"], result.get("geoFenceSchedule"), device)
                )
            return await self._verify_written_schedule(device, body, False, matches)

    async def set_schedule_enabled(self, device_id, enabled, expected_revision):
        """Use the app's Schedule/Status endpoint, not thermostat hold commands."""
        device = self._schedule_device(device_id, False)
        async with self._command_lock:
            raw = await self._read_schedule(device, False)
            try:
                _check_revision(raw, expected_revision)
                if type(enabled) is not bool:
                    raise CommandError("enabled must be a boolean")
                if raw.get("scheduleType") not in ("Timed", "Geofence", "None") or raw.get("scheduleSubType") not in ("EMEA", "None", None):
                    raise CommandError("Load a supported heating schedule status first")
                # A status-only toggle does not edit/create a routine. Do not
                # reject an existing sparse week or a disabled `None` response.
                # Period-edit validation belongs to the timed writer only.
                if not device.location_id.isdecimal():
                    raise CommandError("Resideo did not report a numeric location ID")
            except CommandError as err:
                raise CommandError(f"{err}; no write was sent") from err
            status = "Resume" if enabled else "Pause"
            # Gson's ScheduleOnOffRequestModel serializes its unannotated
            # location field as `a`, plus @SerializedName DeviceIds/ScheduleStatus.
            body = {"a": int(device.location_id), "DeviceIds": [device_id], "ScheduleStatus": status}
            path = f"api/v2/locations/{quote(device.location_id, safe='')}/Schedule/Status"
            await self._request("PUT", path, body)

            async def read():
                devices = parse_locations(await self._request("GET", "api/v4/locations"))
                self.devices = devices
                fresh = self._schedule_device(device_id, False)
                return {"schedule_enabled": fresh.schedule_enabled, "schedule_status": fresh.raw.get("scheduleStatus")}

            actual, verified, attempts, error = await verify_readback(read, lambda value: value["schedule_enabled"] is enabled)
            fresh = self.devices.get(device_id, device)
            refreshed = False
            if verified:
                try:
                    raw = await self._read_schedule(fresh, False)
                    refreshed = True
                except ResideoError:
                    pass
            result = verification_result({**present(raw, fresh, False), **(actual or {"schedule_enabled": None})}, verified, attempts, error)
            result["verification_scope"] = "native_schedule_status"
            result["schedule_content_refreshed"] = refreshed
            if verified and not refreshed:
                result.update(write_supported=False, message="Native schedule On/Off was confirmed, but the routine could not be refreshed. Load from Resideo before editing.")
            return result
