"""Mode/hold commands: traced bodies, validation and confirmed readback only."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from custom_components.resideo_native.protocol.errors import CommandError, CannotConnect
from custom_components.resideo_native.protocol.schedules import DAYS, revision
from dhw_fixtures import dhw_locations
from test_schedules import client, raw


def profile():
    return {"homePeriod": {"heatSetPoint": 68, "coolSetPoint": 0},
            "awayPeriod": {"heatSetPoint": 60.8, "coolSetPoint": 0}}


async def test_geofence_body_uses_one_parent_and_user_display_temperatures(client, raw):
    result = {"scheduleType": "Geofence", "geoFenceSchedule": profile()}
    client._request.side_effect = [raw, None, result]
    response = await client.set_schedule_mode("T6R-parent", "Geofence", revision(raw),
        confirm_change=True, geofence={"home_temperature": 20, "away_temperature": 16})
    method, path, body = client._request.call_args_list[1].args
    assert method == "PUT" and path == "api/v3/locations/123/ThermostatSchedule"
    assert body == {"scheduleType": "Geofence", "deviceIDs": ["T6R-parent"], "geoFenceSchedule": profile()}
    assert response["schedule_type"] == "Geofence"
    assert response["geofence_settings"] == {"home_temperature": 20, "away_temperature": 16, "has_sleep": False}


async def test_geofence_preserves_returned_sleep_and_original_response(client, raw):
    raw["geoFenceSchedule"] = profile()
    sleep = {"triggers": [{"startTime": "22:00:00", "endTime": "06:00:00"}], "heatSetPoint": 62.6, "coolSetPoint": 0}
    raw["geoFenceSchedule"]["sleepMode"] = sleep
    before = deepcopy(raw)
    saved = {"scheduleType": "Geofence", "geoFenceSchedule": deepcopy(raw["geoFenceSchedule"])}
    client._request.side_effect = [raw, None, saved]
    await client.set_schedule_mode("T6R-parent", "Geofence", revision(raw), confirm_change=True)
    assert client._request.call_args_list[1].args[2]["geoFenceSchedule"]["sleepMode"] == sleep
    assert raw == before


async def test_timed_mode_accepts_only_two_active_days_but_keeps_seven_lists(client):
    source = {"scheduleType": "Geofence", "geoFenceSchedule": profile()}
    days = {d: [] for d in DAYS}
    days["Monday"] = [{"time": "08:00", "temperature": 20}]
    days["Sunday"] = [{"time": "09:00", "temperature": 19}]
    sent = None
    async def request(method, path, body=None):
        nonlocal sent
        if method == "PUT": sent = body; return None
        return source if sent is None else sent
    client._request.side_effect = request
    response = await client.set_schedule_mode("T6R-parent", "Timed", revision(source), confirm_change=True, days=days)
    assert sent["scheduleSubType"] == "EMEA" and sent["deviceIDs"] == ["T6R-parent"]
    assert len(sent["timedSchedule"]["days"]) == 7
    assert sum(bool(d["periods"]) for d in sent["timedSchedule"]["days"]) == 2
    assert all(not {"periodType", "isCancelled"} & set(p) for d in sent["timedSchedule"]["days"] for p in d["periods"])
    assert response["schedule_type"] == "Timed"


@pytest.mark.parametrize("mode,kwargs", [
    ("None", {"confirm_change": True}),
    ("Geofence", {}),
    ("Geofence", {"confirm_change": True}),
    ("Geofence", {"confirm_change": True, "geofence": {"home_temperature": True, "away_temperature": 16}}),
    ("Geofence", {"confirm_change": True, "geofence": {"home_temperature": 100, "away_temperature": 16}}),
    ("Geofence", {"confirm_change": True, "geofence": {"home_temperature": float("nan"), "away_temperature": 16}}),
    ("Geofence", {"confirm_change": True, "geofence": {"home_temperature": 20, "away_temperature": 16, "deviceIDs": ["other"]}}),
    ("Timed", {"confirm_change": True, "days": {"Monday": []}}),
    ("Timed", {"confirm_change": True, "days": {d: [] for d in DAYS}}),
])
async def test_invalid_mode_commands_never_put(client, raw, mode, kwargs):
    client._request.return_value = raw
    with pytest.raises(CommandError, match="no write was sent"):
        await client.set_schedule_mode("T6R-parent", mode, revision(raw), **kwargs)
    assert client._request.await_count == 1


async def test_mode_change_checks_revision_even_with_consent(client, raw):
    client._request.return_value = raw
    with pytest.raises(CommandError, match="changed.*no write was sent"):
        await client.set_schedule_mode("T6R-parent", "Geofence", "old", confirm_change=True, geofence={"home_temperature": 20, "away_temperature": 16})
    assert client._request.await_count == 1


@pytest.mark.parametrize("enabled", [False, True])
async def test_native_schedule_switch_uses_status_endpoint_not_hold(client, raw, enabled):
    locations = dhw_locations()
    parent = next(d for d in locations[0]["devices"] if d.get("deviceID") == "T6R-parent")
    parent["scheduleStatus"] = "Resume" if enabled else "Pause"
    before = deepcopy(raw)
    client._request.side_effect = [raw, None, locations, raw]
    result = await client.set_schedule_enabled("T6R-parent", enabled, revision(raw))
    assert client._request.call_args_list[1].args == ("PUT", "api/v2/locations/123/Schedule/Status", {"a": 123, "DeviceIds": ["T6R-parent"], "ScheduleStatus": "Resume" if enabled else "Pause"})
    assert result["schedule_enabled"] is enabled
    assert result["verification_status"] == "verified"
    assert all("/hold" not in c.args[1] for c in client._request.call_args_list)
    assert raw == before


async def test_native_switch_mismatch_is_unconfirmed_and_never_replays(client, raw):
    client._request.side_effect = [raw, None, *[dhw_locations() for _ in range(5)]]
    result = await client.set_schedule_enabled("T6R-parent", False, revision(raw))
    assert result["status"] == "readback_unconfirmed"
    assert result["schedule_enabled"] is None
    assert sum(c.args[0] == "PUT" for c in client._request.call_args_list) == 1
    client._request.reset_mock()
    client._request.side_effect = [raw, CannotConnect("unknown delivery")]
    with pytest.raises(CannotConnect):
        await client.set_schedule_enabled("T6R-parent", False, revision(raw))
    assert client._request.await_count == 2


async def test_wrong_mode_readback_does_not_report_success(client, raw):
    client._request.side_effect = [raw, None, *[raw for _ in range(5)]]
    result = await client.set_schedule_mode("T6R-parent", "Geofence", revision(raw), confirm_change=True, geofence={"home_temperature": 20, "away_temperature": 16})
    assert result["status"] == "readback_unconfirmed"
    assert result["schedule_type"] == "Timed"
    assert client._request.await_count == 7


@pytest.mark.parametrize("change", ["bad_type", "stale", "partner", "bad_subtype"])
async def test_following_invalid_requests_do_not_put(client, raw, change):
    source = deepcopy(raw)
    enabled = "false" if change == "bad_type" else True
    if change == "partner": source["scheduleType"] = "Partner"
    if change == "bad_subtype": source["scheduleSubType"] = "NA"
    client._request.return_value = source
    with pytest.raises(CommandError, match="no write was sent"):
        await client.set_schedule_enabled("T6R-parent", enabled, "old" if change == "stale" else revision(source))
    assert client._request.await_count == 1


@pytest.fixture
def sleep_wire():
    # Independently transcribed final Android 6.21.1 legacy serializer shape:
    # ef/c.A0 -> GeofenceScheduleSetting.a -> SleepModeSettingsV3/GeofenceTriggers.
    return json.loads((Path(__file__).parent / "fixtures/geofence_sleep_wire.json").read_text())


def sleep_changes():
    # Maintainer's failing 0.3.0 example: equal Home/Away and overnight sleep.
    return {"home_temperature": 25, "away_temperature": 25,
            "sleep": {"start_time": "22:00", "end_time": "09:00", "temperature": 23}}


async def test_create_sleep_uses_final_native_trigger_body(client, raw, sleep_wire):
    before = deepcopy(raw)
    client._request.side_effect = [raw, None, sleep_wire]
    response = await client.set_schedule_mode("T6R-parent", "Geofence", revision(raw),
        confirm_change=True, geofence=sleep_changes())
    assert client._request.call_args_list[1].args == (
        "PUT", "api/v3/locations/123/ThermostatSchedule", sleep_wire)
    assert response["verification_status"] == "verified"
    assert response["geofence_settings"]["sleep"] == {
        "start_time": "22:00:00", "end_time": "09:00:00", "temperature": 23}
    assert raw == before


async def test_sleep_readback_allows_day_order_and_time_format(client, raw, sleep_wire):
    saved = deepcopy(sleep_wire)
    trigger = saved["geoFenceSchedule"]["sleepMode"]["triggers"][0]
    trigger["days"].reverse()
    trigger.update(startTime="22:00", endTime="09:00")
    client._request.side_effect = [raw, None, saved]
    response = await client.set_schedule_mode("T6R-parent", "Geofence", revision(raw),
        confirm_change=True, geofence=sleep_changes())
    assert response["verification_status"] == "verified"


@pytest.mark.parametrize("changed", ["missing_days", "subset_days", "temperature", "start_time"])
async def test_sleep_readback_checks_days_times_and_temperature_without_replay(client, raw, sleep_wire, changed):
    saved = deepcopy(sleep_wire)
    sleep = saved["geoFenceSchedule"]["sleepMode"]
    trigger = sleep["triggers"][0]
    if changed == "missing_days": trigger.pop("days")
    if changed == "subset_days": trigger["days"] = ["Monday"]
    if changed == "temperature": sleep["heatSetPoint"] = 68
    if changed == "start_time": trigger["startTime"] = "21:00:00"
    client._request.side_effect = [raw, None, *[saved for _ in range(5)]]
    response = await client.set_schedule_mode("T6R-parent", "Geofence", revision(raw),
        confirm_change=True, geofence=sleep_changes())
    assert response["verification_status"] == "unconfirmed"
    assert sum(c.args[0] == "PUT" for c in client._request.call_args_list) == 1


@pytest.mark.parametrize("existing_shape", ["flat", "triggers"])
async def test_edit_sleep_replaces_old_times_with_final_wire_shape(client, raw, sleep_wire, existing_shape):
    existing = {"heatSetPoint": 61.7, "coolSetPoint": 0, "fanSwitch": "Auto"}
    if existing_shape == "flat":
        existing.update(startTime="23:00:00", endTime="06:00:00")
    else:
        existing["triggers"] = [{"days": list(DAYS), "startTime": "23:00:00", "endTime": "06:00:00"}]
    raw.update(scheduleType="Geofence", geoFenceSchedule={**profile(), "sleepMode": existing})
    expected = deepcopy(sleep_wire)
    expected["geoFenceSchedule"]["sleepMode"]["fanSwitch"] = "Auto"
    client._request.side_effect = [raw, None, expected]
    response = await client.set_schedule_mode("T6R-parent", "Geofence", revision(raw),
        confirm_change=True, geofence=sleep_changes())
    assert client._request.call_args_list[1].args[2] == expected
    assert response["verification_status"] == "verified"


async def test_remove_sleep_is_explicit_and_keeps_home_away(client, raw):
    raw['geoFenceSchedule']={**profile(),'sleepMode':{'startTime':'22:00:00','endTime':'06:00:00','heatSetPoint':61.7}}
    saved={'scheduleType':'Geofence','geoFenceSchedule':profile()}
    client._request.side_effect=[raw,None,saved]
    await client.set_schedule_mode('T6R-parent','Geofence',revision(raw),confirm_change=True,geofence={'home_temperature':20,'away_temperature':16,'sleep':None})
    assert client._request.call_args_list[1].args[2]['geoFenceSchedule']==profile()


@pytest.mark.parametrize('sleep',[
    {'start_time':'22:00','end_time':'22:00','temperature':16},
    {'start_time':'24:00','end_time':'06:00','temperature':16},
    {'start_time':'22:00','end_time':'06:00','temperature':True},
    {'start_time':'22:00','end_time':'06:00','temperature':99},
    {'start_time':'22:00','end_time':'06:00'},
    {'start_time':'22:00','end_time':'06:00','temperature':16,'deviceId':'other'},
])
async def test_invalid_sleep_never_sends_put(client, raw, sleep):
    client._request.return_value=raw
    with pytest.raises(CommandError,match='no write was sent'):
        await client.set_schedule_mode('T6R-parent','Geofence',revision(raw),confirm_change=True,geofence={'home_temperature':20,'away_temperature':16,'sleep':sleep})
    assert client._request.await_count==1
