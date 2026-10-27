"""Legacy Jasper schedule API, traced from Android 6.21.1 (ef/c, Ce/c)."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from urllib.parse import quote

from .errors import CommandError, InvalidResponse
from .schedule_rules import DAYS, geofence_profile, validate_heating_week
from .schedule_readback import verification_result, verify_readback


def response_structure(raw):
    """Report expected field names/types only; never response values or arbitrary keys."""
    known = {
        "deviceID",
        "deviceId",
        "scheduleType",
        "scheduleSubType",
        "timedSchedule",
        "geoFenceSchedule",
        "days",
        "periods",
        "data",
        "schedule",
        "schedules",
        "message",
        "error",
        "errors",
        "status",
        "code",
    }
    if not isinstance(raw, dict):
        return {"type": type(raw).__name__}
    return {
        "type": "object",
        "fields": {k: type(v).__name__ for k, v in raw.items() if k in known},
        "other_field_count": len(set(raw) - known),
    }


def revision(raw):
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def time_value(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d(?::00)?", value
    ):
        raise CommandError(
            "Use local wall-clock times HH:MM, with optional :00 seconds"
        )
    return value[:5] + ":00"


def schedule_days(raw):
    if not isinstance(raw, dict):
        raise InvalidResponse("Unexpected schedule response; no write was sent")
    timed = raw.get("timedSchedule")
    if timed is None:
        return []
    if not isinstance(timed, dict) or not isinstance(timed.get("days"), list):
        raise InvalidResponse("Unexpected timedSchedule shape; no write was sent")
    days = timed["days"]
    seen = set()
    for day in days:
        if (
            not isinstance(day, dict)
            or day.get("day") not in DAYS
            or day["day"] in seen
            or not isinstance(day.get("periods"), list)
            or any(not isinstance(p, dict) for p in day["periods"])
        ):
            raise InvalidResponse(
                "Unexpected schedule day structure; no write was sent"
            )
        seen.add(day["day"])
    return days


def present(raw, device, hot_water):
    """Readable/editable periods in the thermostat display unit, without identifiers."""
    days = {}
    for day in schedule_days(raw):
        periods = []
        for p in day["periods"]:
            # Cancellation flags belong to the NA period schema. EMEA's
            # native period list is authoritative; its PUT forbids this flag.
            if (
                not hot_water
                and raw.get("scheduleSubType") == "NA"
                and p.get("isCancelled") is True
            ):
                continue
            item = {"time": p.get("startTime")}
            if hot_water:
                item["state"] = p.get("dhwState")
            else:
                item["temperature"] = device._temperature_from_wire(
                    p.get("heatSetPoint", p.get("heatSetpoint"))
                )
            periods.append(item)
        days[day["day"]] = periods
    return {
        "revision": revision(raw),
        "temperature_unit": device.unit if not hot_water else None,
        "schedule_type": raw.get("scheduleType"),
        "native_schema": {
            "schedule_subtype": raw.get("scheduleSubType")
            if raw.get("scheduleSubType") in ("EMEA", "NA", "None")
            else None,
            "period_fields": sorted(
                {
                    key
                    for day in schedule_days(raw)
                    for period in day["periods"]
                    for key in period
                    if key
                    in {
                        "startTime",
                        "heatSetPoint",
                        "heatSetpoint",
                        "coolSetPoint",
                        "coolSetpoint",
                        "isCancelled",
                        "periodType",
                        "periodName",
                        "fanSwitch",
                        "schedSysSwitch",
                        "priority",
                        "dhwState",
                    }
                }
            ),
        },
        "days": days,
        "schedule_kind": "hot_water" if hot_water else "heating",
        "requires_conversion": not hot_water and raw.get("scheduleType") == "Geofence",
        # Timed still identifies an existing routine when empty. Keep it
        # readable for repair; writes validate both minimum day groups below.
        "requires_full_week": (
            not any(days.values())
            and (hot_water or raw.get("scheduleType") != "Timed")
        )
        or (not hot_water and raw.get("scheduleType") == "Geofence"),
        "write_supported": hot_water
        or (
            raw.get("scheduleType") in ("Timed", "None", "Geofence")
            and raw.get("scheduleSubType") in ("EMEA", "None", None)
        ),
        "temperature_limits": list(device.temperature_limits("heat"))
        if not hot_water
        else None,
        "max_periods_per_day": 6,
        "time_basis": "thermostat_local",
        "minimum_weekday_days": 0 if hot_water else 1,
        "minimum_weekend_days": 0 if hot_water else 1,
        "geofence_settings": None if hot_water else geofence_profile(raw, device),
        "schedule_enabled": None if hot_water else device.schedule_enabled,
        "time_step_minutes": 10 if hot_water else device.schedule_time_step,
        "schedule_controls_supported": not hot_water
        and raw.get("scheduleType") in ("Timed", "Geofence", "None")
        and raw.get("scheduleSubType") in ("EMEA", "None", None),
        "schedule_following": (
            False if not hot_water and (device.schedule_enabled is False or raw.get("scheduleType") == "None")
            else device.values.get("thermostatSetpointStatus") == "NoHold"
            if not hot_water and device.schedule_enabled is True
            and device.values.get("thermostatSetpointStatus") in ("NoHold", "PermanentHold", "TemporaryHold", "HoldUntil")
            else None
        ),
    }


def merge_days(raw, changes, device, hot_water):
    """Validate a partial week and preserve untouched native days/period metadata."""
    existing = {d["day"]: deepcopy(d) for d in schedule_days(raw)}
    if not isinstance(changes, dict) or not changes or set(changes) - set(DAYS):
        raise CommandError("days must map Monday through Sunday to period lists")
    creating = not any(d["periods"] for d in existing.values()) and (
        hot_water or raw.get("scheduleType") != "Timed"
    )
    if creating and set(changes) != set(DAYS):
        raise CommandError("Creating a schedule requires all seven days")
    # An explicit empty list clears this day of an existing routine. Keep the
    # day in the PUT so removal is distinguished from an untouched/omitted day.
    # New routines and geofence conversions retain their full-week validation.
    minimum = 1 if hot_water and creating else 0
    for name, periods in changes.items():
        if not isinstance(periods, list) or not minimum <= len(periods) <= 6:
            raise CommandError(
                f"{name}: provide {minimum}–6 ordered periods for this edited day"
            )
        original = existing.get(name, {"day": name, "periods": []})
        old = original["periods"]
        new = []
        previous = ""
        for index, p in enumerate(periods):
            keys = {"time", "state"} if hot_water else {"time", "temperature"}
            if not isinstance(p, dict) or set(p) != keys:
                raise CommandError(f"Each period requires exactly {sorted(keys)}")
            start = time_value(p["time"])
            step = 10 if hot_water else device.schedule_time_step
            if step and (int(start[:2]) * 60 + int(start[3:5])) % step:
                raise CommandError(f"{name}: times must use {step}-minute increments")
            if start <= previous:
                raise CommandError("Periods must have unique increasing times")
            previous = start
            item = deepcopy(old[index]) if index < len(old) else {}
            item["startTime"] = start
            if hot_water:
                if p["state"] not in ("On", "Off"):
                    raise CommandError("Hot-water state must be On or Off")
                item["dhwState"] = p["state"]
            else:
                value = device.validate_temperature(p["temperature"], "heat")
                if isinstance(p["temperature"], bool):
                    raise CommandError("Temperature must be numeric")
                item["heatSetPoint"] = device.temperature_to_wire(value)
                # App's Jasper period builder emits 0 for an absent cooling
                # setpoint on heating-only devices (Y9/a.c -> qi/d.v).
                item.setdefault("coolSetPoint", item.get("coolSetpoint", 0))
                item.pop("heatSetpoint", None)
                item.pop("coolSetpoint", None)
                # Jasper schedules may omit cancellation entirely. Preserve
                # the native schema instead of injecting another model's flag.
                if "isCancelled" in item:
                    item["isCancelled"] = False
                item.setdefault("periodType", f"P{index + 1}")
            new.append(item)
        original["periods"] = new
        existing[name] = original
    result = [existing[d] for d in DAYS if d in existing]
    if not hot_water:
        validate_heating_week({d["day"]: d["periods"] for d in result})
    return result


def timed_body(raw, changes, device):
    """The EMEA writer excludes read-only period flags across every day."""
    if raw.get("scheduleSubType") not in ("EMEA", "None", None):
        raise CommandError("Only EMEA heating schedules are supported")
    days = merge_days(raw, changes, device, False)
    for day in days:
        for period in day["periods"]:
            period.pop("periodType", None)
            period.pop("isCancelled", None)
    return {
        "scheduleType": "Timed", "scheduleSubType": "EMEA",
        "deviceIDs": [device.device_id], "timedSchedule": {"days": days},
    }


class ScheduleClientMixin:
    def _schedule_device(self, device_id, hot_water):
        device = (
            self._hot_water_device(device_id) if hot_water else self._device(device_id)
        )
        if str(device.raw.get("deviceType") or device.model).casefold() != "jasper":
            raise CommandError(
                "Schedule support is limited to legacy Jasper thermostats"
            )
        if not hot_water and (
            "Heat" not in device.allowed_modes or "Cool" in device.allowed_modes
        ):
            raise CommandError("This test build supports heating-only Jasper schedules")
        return device

    async def _read_schedule(self, device, hot_water):
        path = (
            self._path(device, "dhw/schedule", "v3/")
            if hot_water
            else self._path(device, "Schedule", "v4/")
        )
        raw = await self._request("GET", path)
        schedule_days(raw)
        recognized_geofence = (
            not hot_water
            and raw.get("scheduleType") == "Geofence"
            and isinstance(raw.get("geoFenceSchedule"), dict)
        )
        if (
            "timedSchedule" not in raw
            and not recognized_geofence
            and (hot_water or raw.get("scheduleType") != "None")
        ):
            raise InvalidResponse(
                "Schedule response has no recognized schedule field; no write was sent. Structure: "
                + json.dumps(response_structure(raw), sort_keys=True)
            )
        return raw

    async def get_schedule(self, device_id, *, hot_water=False):
        device = self._schedule_device(device_id, hot_water)
        async with self._command_lock:
            try:
                raw = await self._read_schedule(device, hot_water)
            except InvalidResponse as err:
                if "Structure: " not in str(err):
                    raise
                return {
                    "status": "unrecognized_response",
                    "write_supported": False,
                    "response_structure": json.loads(
                        str(err).split("Structure: ", 1)[1]
                    ),
                    "message": "No recognized schedule data returned. This does not establish that no schedule exists. No write was sent.",
                }
            return present(raw, device, hot_water)

    async def set_schedule(
        self,
        device_id,
        days,
        expected_revision,
        *,
        hot_water=False,
        confirm_conversion=False,
    ):
        device = self._schedule_device(device_id, hot_water)
        async with self._command_lock:
            raw = await self._read_schedule(device, hot_water)
            try:
                if not isinstance(
                    expected_revision, str
                ) or expected_revision != revision(raw):
                    raise CommandError(
                        "Schedule changed or revision is missing; fetch it again before saving"
                    )
                if type(confirm_conversion) is not bool:
                    raise CommandError("confirm_conversion must be a boolean")
                converting = not hot_water and raw.get("scheduleType") == "Geofence"
                if converting:
                    if not confirm_conversion:
                        raise CommandError(
                            "Geofence conversion requires explicit confirm_conversion: true"
                        )
                    if not isinstance(days, dict) or set(days) != set(DAYS):
                        raise CommandError(
                            "Converting geofence to timed requires all seven days"
                        )
                elif not hot_water and raw.get("scheduleType") not in ("Timed", "None"):
                    raise CommandError("Partner/unknown schedules cannot be replaced")
                # A conversion is a new full-week timed routine, not a merge with
                # any inactive/stale timed data retained alongside geofencing.
                source = {"timedSchedule": {"days": []}} if converting else raw
                days = merge_days(source, days, device, hot_water)
                if hot_water:
                    body = {"timedSchedule": {"days": days}}
                    path = self._path(device, "dhw/schedule", "v3/")
                else:
                    subtype = raw.get("scheduleSubType")
                    if subtype not in ("EMEA", "None", None):
                        raise CommandError("Only EMEA heating schedules are supported")
                    # GET and PUT schemas differ. Resideo rejects these fields
                    # anywhere in an EMEA write, including untouched days.
                    for day in days:
                        # Preserve the returned EMEA period list, including an
                        # untouched empty day. Only edited days are validated by
                        # merge_days; first creation still needs all seven days.
                        for period in day["periods"]:
                            period.pop("periodType", None)
                            period.pop("isCancelled", None)
                    body = {
                        "scheduleType": "Timed",
                        "scheduleSubType": "EMEA",
                        "deviceIDs": [device.device_id],
                        "timedSchedule": {"days": days},
                    }
                    path = f"api/v3/locations/{quote(device.location_id, safe='')}/ThermostatSchedule"
            except CommandError as err:
                raise CommandError(f"{err}; no write was sent") from err
            await self._request("PUT", path, body)
            return await self._verify_written_schedule(device, body, hot_water)

    async def _verify_written_schedule(self, device, body, hot_water, raw_matcher=None):
        wanted = present(body, device, hot_water)

        def differences(result):
            actual = present(result, device, hot_water)
            def comparable(items):
                return sorted([
                    (time_value(p["time"]), p["state"] if hot_water else round(p["temperature"], 3))
                    for p in items
                ])
            changed = []
            for d in DAYS:
                try:
                    equal = comparable(actual["days"].get(d, [])) == comparable(wanted["days"].get(d, []))
                except (CommandError, TypeError, ValueError):
                    equal = False
                if not equal:
                    changed.append(d)
            return changed

        def matches(result):
            if raw_matcher is not None:
                return raw_matcher(result)
            if not hot_water and result.get("scheduleType") != body.get("scheduleType"):
                return False
            return not differences(result)

        observed, verified, attempts, error = await verify_readback(
            lambda: self._read_schedule(device, hot_water), matches
        )
        actual = present(observed, device, hot_water) if observed is not None else None
        result = verification_result(actual, verified, attempts, error)
        if not verified and raw_matcher is None:
            result["requested_days"] = wanted["days"]
            result["mismatched_days"] = differences(observed) if observed is not None else list(DAYS)
        return result
