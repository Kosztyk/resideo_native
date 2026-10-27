"""Jasper timed-week rules and the app's geofence temperature profile."""

from copy import deepcopy
import re

from .errors import CommandError

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
# GeofenceTriggers uses hd/g.values(), whose native enum starts on Sunday.
SLEEP_DAYS = ("Sunday", *DAYS[:6])
WEEK_COVERAGE_ERROR = (
    "Keep at least one weekday (Monday–Friday) and one weekend day "
    "(Saturday or Sunday) with a period. Turn the Heating schedule switch Off to disable scheduling."
)


def validate_heating_week(days):
    """Match the EMEA app minimum reported by the maintainer; never add defaults."""
    if not any(days.get(d) for d in DAYS[:5]) or not any(days.get(d) for d in DAYS[5:]):
        raise CommandError(WEEK_COVERAGE_ERROR)


def sleep_profile(geo, device):
    sleep = geo.get("sleepMode") if isinstance(geo, dict) else None
    if not isinstance(sleep, dict):
        return None
    times = sleep
    if isinstance(sleep.get("triggers"), list) and len(sleep["triggers"]) == 1:
        times = sleep["triggers"][0]
    try:
        return {
            "start_time": sleep_time(times.get("startTime")),
            "end_time": sleep_time(times.get("endTime")),
            "temperature": device.validate_temperature(device._temperature_from_wire(sleep.get("heatSetPoint")), "heat"),
        }
    except (CommandError, AttributeError, TypeError):
        return None


def sleep_time(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::00)?", value):
        raise CommandError("Sleep times must use HH:MM with optional :00 seconds")
    return value[:5] + ":00"


def _sleep_days(sleep):
    """Recognize the single-trigger day coverage without inventing missing days."""
    if not isinstance(sleep, dict):
        return None
    triggers = sleep.get("triggers")
    if not isinstance(triggers, list) or len(triggers) != 1 or not isinstance(triggers[0], dict):
        return None
    days = triggers[0].get("days")
    if not isinstance(days, list) or not days or any(not isinstance(d, str) or d not in DAYS for d in days):
        return None
    if len(days) != len(set(days)):
        return None
    return frozenset(days)


def sleep_readback_matches(expected, actual, device):
    """Compare sleep values and day coverage, preserving opaque profiles exactly."""
    expected_sleep = expected.get("sleepMode") if isinstance(expected, dict) else None
    actual_sleep = actual.get("sleepMode") if isinstance(actual, dict) else None
    if expected_sleep == actual_sleep:
        return True
    profile = sleep_profile(expected, device)
    days = _sleep_days(expected_sleep)
    return (
        profile is not None
        and days is not None
        and profile == sleep_profile(actual, device)
        and days == _sleep_days(actual_sleep)
    )


def geofence_profile(raw, device):
    """Expose temperatures only, without account or phone geofence information."""
    geo = raw.get("geoFenceSchedule")
    if not isinstance(geo, dict):
        return None
    result = {}
    for field, key in (("homePeriod", "home_temperature"), ("awayPeriod", "away_temperature")):
        period = geo.get(field)
        value = device._temperature_from_wire(period.get("heatSetPoint")) if isinstance(period, dict) else None
        if value is None:
            return None
        try:
            result[key] = device.validate_temperature(value, "heat")
        except CommandError:
            return None
    result["has_sleep"] = isinstance(geo.get("sleepMode"), dict)
    if result["has_sleep"]:
        result["sleep"] = sleep_profile(geo, device)
    return result


def geofence_settings(raw, device, changes=None):
    """Build the Y9/a.b / ef/c.A0 shape, retaining a returned sleep profile."""
    original = raw.get("geoFenceSchedule")
    settings = deepcopy(original) if isinstance(original, dict) else {}
    if set(settings) - {"homePeriod", "awayPeriod", "sleepMode"}:
        raise CommandError("Unrecognized geofence fields; configure this profile in the Resideo app")
    if changes is None:
        profile = geofence_profile(raw, device)
        if profile is None:
            raise CommandError("Enter both Home and Away temperatures before selecting Geofence")
        changes = {k: profile[k] for k in ("home_temperature", "away_temperature")}
    if not isinstance(changes, dict) or not {"home_temperature", "away_temperature"} <= set(changes) or set(changes) - {"home_temperature", "away_temperature", "sleep"}:
        raise CommandError("Geofence requires Home/Away temperatures and optional sleep settings")
    for field, key in (("homePeriod", "home_temperature"), ("awayPeriod", "away_temperature")):
        value = changes[key]
        if isinstance(value, bool):
            raise CommandError("Geofence temperatures must be numeric")
        value = device.validate_temperature(value, "heat")
        period = settings.get(field)
        period = deepcopy(period) if isinstance(period, dict) else {}
        if set(period) - {"heatSetPoint", "coolSetPoint", "fanSwitch", "priority", "schedSysSwitch"}:
            raise CommandError("Unrecognized geofence period fields; use the Resideo app")
        period["heatSetPoint"] = device.temperature_to_wire(value)
        # The app's heating-only builder converts a missing cooling value to 0.
        period.setdefault("coolSetPoint", 0)
        settings[field] = period
    if "sleep" in changes:
        sleep = changes["sleep"]
        if sleep is None:
            settings.pop("sleepMode", None)
        else:
            if not isinstance(sleep, dict) or set(sleep) != {"start_time", "end_time", "temperature"}:
                raise CommandError("Sleep requires start_time, end_time and temperature")
            start, end = sleep_time(sleep["start_time"]), sleep_time(sleep["end_time"])
            if start == end:
                raise CommandError("Sleep start and end must be different")
            step = device.schedule_time_step
            if step and any((int(t[:2]) * 60 + int(t[3:5])) % step for t in (start, end)):
                raise CommandError(f"Sleep times must use {step}-minute increments")
            value = sleep["temperature"]
            if isinstance(value, bool):
                raise CommandError("Sleep temperature must be numeric")
            value = device.validate_temperature(value, "heat")
            original_sleep = settings.get("sleepMode")
            original_sleep = original_sleep if isinstance(original_sleep, dict) else {}
            # ef/c.A0 calls GeofenceScheduleSetting.a(), which converts the
            # internal flat SleepModeSettings into SleepModeSettingsV3 before
            # serialization. GeofenceTriggers supplies all seven native days.
            settings["sleepMode"] = {
                **{k: original_sleep[k] for k in ("fanSwitch", "priority", "schedSysSwitch") if k in original_sleep},
                "triggers": [{"days": list(SLEEP_DAYS), "startTime": start, "endTime": end}],
                "heatSetPoint": device.temperature_to_wire(value),
                "coolSetPoint": original_sleep.get("coolSetPoint", 0),
            }
    if settings.get("sleepMode") is None:
        settings.pop("sleepMode", None)
    elif not isinstance(settings["sleepMode"], dict):
        raise CommandError("Unrecognized geofence sleep profile; use the Resideo app")
    return settings
