"""Regressions from the 0.2.3 tester: delayed writes and the ignored 07:05 edit."""

from copy import deepcopy

import pytest

from custom_components.resideo_native.protocol.errors import CommandError
from custom_components.resideo_native.protocol.schedules import DAYS, revision
from test_schedules import client, raw
from dhw_fixtures import dhw_locations


@pytest.mark.parametrize("hot", [False, True])
async def test_stale_reads_then_applied_deletion_are_verified_without_replaying_put(client, raw, hot):
    source = deepcopy(raw)
    if hot:
        source = {"timedSchedule": {"days": [{"day": d, "periods": [{"startTime": "07:00:00", "dhwState": "On"}, {"startTime": "08:00:00", "dhwState": "Off"}]} for d in DAYS]}}
    saved = deepcopy(source)
    saved["timedSchedule"]["days"][-1]["periods"] = []
    client._request.side_effect = [source, None, source, source, saved]
    result = await client.set_schedule("T6R-parent", {"Sunday": []}, revision(source), hot_water=hot)
    assert result["verification_status"] == "verified"
    assert result["verification_attempts"] == 3
    assert result["days"]["Sunday"] == []
    assert sum(c.args[0] == "PUT" for c in client._request.call_args_list) == 1
    assert all(c.args[0] == "GET" for c in client._request.call_args_list[2:])


async def test_dhw_0705_is_rejected_before_any_put_and_0710_is_verified(client):
    raw = {"timedSchedule": {"days": [{"day": d, "periods": [{"startTime": "07:00:00", "dhwState": "On"}, {"startTime": "08:00:00", "dhwState": "Off"}]} for d in DAYS]}}
    client._request.return_value = raw
    change = {"Sunday": [{"time": "07:05", "state": "On"}, {"time": "08:00", "state": "Off"}]}
    with pytest.raises(CommandError, match="10-minute.*no write was sent"):
        await client.set_schedule("T6R-parent", change, revision(raw), hot_water=True)
    assert client._request.await_count == 1
    change["Sunday"][0]["time"] = "07:10"
    saved = deepcopy(raw)
    saved["timedSchedule"]["days"][-1]["periods"][0]["startTime"] = "07:10:00"
    client._request.reset_mock()
    client._request.side_effect = [raw, None, raw, saved]
    result = await client.set_schedule("T6R-parent", change, revision(raw), hot_water=True)
    assert result["verification_status"] == "verified"
    assert result["days"]["Sunday"][0]["time"] == "07:10:00"


async def test_dhw_unapplied_valid_time_never_returns_verified(client):
    raw = {"timedSchedule": {"days": [{"day": "Sunday", "periods": [{"startTime": "07:00:00", "dhwState": "On"}]}]}}
    client._request.side_effect = [raw, None, *[raw for _ in range(5)]]
    result = await client.set_schedule("T6R-parent", {"Sunday": [{"time": "07:10", "state": "On"}]}, revision(raw), hot_water=True)
    assert result["status"] == "readback_unconfirmed"
    assert result["days"]["Sunday"][0]["time"] == "07:00:00"
    assert result["requested_days"]["Sunday"][0]["time"] == "07:10:00"
    assert result["mismatched_days"] == ["Sunday"]


async def test_schedule_toggle_waits_for_native_status_and_ignores_hold(client, raw):
    before = dhw_locations()
    after = deepcopy(before)
    for locs, status in ((before, "Resume"), (after, "Pause")):
        device = next(d for d in locs[0]["devices"] if d.get("deviceID") == "T6R-parent")
        device["scheduleStatus"] = status
        device["thermostat"]["changeableValues"]["thermostatSetpointStatus"] = "NoHold"
    client._request.side_effect = [raw, None, before, after, raw]
    result = await client.set_schedule_enabled("T6R-parent", False, revision(raw))
    assert result["schedule_enabled"] is False
    assert result["schedule_following"] is False
    assert client.devices["T6R-parent"].values["thermostatSetpointStatus"] == "NoHold"
    assert result["verification_attempts"] == 2
    assert all("/hold" not in c.args[1] for c in client._request.call_args_list)


def test_missing_native_status_does_not_infer_off_from_a_hold(client):
    device = client.devices["T6R-parent"]
    device.raw.pop("scheduleStatus", None)
    device.raw["thermostat"]["changeableValues"]["thermostatSetpointStatus"] = "PermanentHold"
    assert device.schedule_enabled is None


async def test_reported_heating_time_step_is_respected_without_rounding(client, raw):
    client.devices["T6R-parent"].raw["allowedTimeIncrements"] = 15
    client._request.return_value = raw
    with pytest.raises(CommandError, match="15-minute.*no write was sent"):
        await client.set_schedule("T6R-parent", {"Sunday": [{"time": "07:05", "temperature": 19}]}, revision(raw))
    assert client._request.await_count == 1


async def test_semantic_readback_ignores_metadata_order_and_seconds_format(client, raw):
    saved = deepcopy(raw)
    saved["timedSchedule"]["days"][-1]["periods"][0]["heatSetPoint"] = 67.1
    saved["timedSchedule"]["days"].reverse()
    for day in saved["timedSchedule"]["days"]:
        day["periods"].reverse()
        for period in day["periods"]:
            period["startTime"] = period["startTime"][:5]
            period["periodType"] = "metadata-only-change"
    client._request.side_effect = [raw, None, saved]
    result = await client.set_schedule("T6R-parent", {"Sunday": [{"time": "06:30", "temperature": 19.5}, {"time": "22:30", "temperature": 16}]}, revision(raw))
    assert result["verification_status"] == "verified"
    assert result["verification_attempts"] == 1
