"""Schedule reads, safe partial updates, exact APK routes and cloud readback."""

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from custom_components.resideo_native.protocol.client import NativeClient
from custom_components.resideo_native.protocol.device import parse_locations
from custom_components.resideo_native.protocol.errors import CommandError, CannotConnect
from custom_components.resideo_native.protocol.schedules import (
    DAYS,
    present,
    revision,
    merge_days,
)
from dhw_fixtures import dhw_locations


@pytest.fixture
def client():
    c = NativeClient(None, None)
    c.devices = parse_locations(dhw_locations())
    c._request = AsyncMock()
    return c


@pytest.fixture
def raw():
    return {
        "scheduleType": "Timed",
        "scheduleSubType": "EMEA",
        "timedSchedule": {
            "days": [
                {
                    "day": d,
                    "periods": [
                        {
                            "startTime": "06:30:00",
                            "heatSetPoint": 66.2,
                            "coolSetPoint": 0,
                            "periodType": "P1",
                            "isCancelled": False,
                        },
                        {
                            "startTime": "22:30:00",
                            "heatSetPoint": 60.8,
                            "coolSetPoint": 0,
                            "periodType": "P2",
                            "isCancelled": False,
                        },
                    ],
                }
                for d in DAYS
            ]
        },
    }


async def test_get_heating(client, raw):
    client._request.return_value = raw
    result = await client.get_schedule("T6R-parent")
    assert result["days"]["Monday"][0]["temperature"] == 19
    assert result["revision"] == revision(raw)
    path = client._request.call_args.args[1]
    assert path.endswith("/devices/T6R-parent/Schedule") and path.startswith("api/v4/")
    assert client._request.call_args.args[0] == "GET"


async def test_edit_preserves_other_days_and_targets_one_zone(client, raw):
    d = client.devices["T6R-parent"]
    changes = {
        "Monday": [
            {"time": "08:00", "temperature": 20},
            {"time": "22:00", "temperature": 16},
        ]
    }
    merged = merge_days(raw, changes, d, False)
    saved = {**raw, "timedSchedule": {"days": merged}}
    client._request.side_effect = [raw, None, saved]
    result = await client.set_schedule(d.device_id, changes, revision(raw))
    method, path, body = client._request.call_args_list[1].args
    assert (
        method == "PUT"
        and path.endswith("/ThermostatSchedule")
        and path.startswith("api/v3/")
    )
    assert body["deviceIDs"] == [d.device_id]
    assert body["timedSchedule"]["days"][0]["periods"][0]["heatSetPoint"] == 68
    expected_other_days = deepcopy(raw["timedSchedule"]["days"][1:])
    for day in expected_other_days:
        for period in day["periods"]:
            period.pop("periodType", None)
            period.pop("isCancelled", None)
    assert body["timedSchedule"]["days"][1:] == expected_other_days
    assert result["days"]["Monday"][0]["temperature"] == 20
    assert raw["timedSchedule"]["days"][0]["periods"][0]["startTime"] == "06:30:00"


async def test_stale_revision_sends_no_write(client, raw):
    client._request.return_value = raw
    with pytest.raises(CommandError, match="changed"):
        await client.set_schedule("T6R-parent", {"Monday": []}, "old")
    assert client._request.await_count == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"Funday": []},
        {"Monday": None},
        {"Monday": [{"time": "25:00", "temperature": 20}]},
        {"Monday": [{"time": "08:00", "temperature": 100}]},
        {"Monday": [{"time": "08:00", "temperature": True}]},
        {"Monday": [{"time": "08:00", "temperature": float("nan")}]},
        {
            "Monday": [
                {"time": "09:00", "temperature": 20},
                {"time": "08:00", "temperature": 20},
            ]
        },
        {"Monday": [{"time": "08:00", "temperature": 20, "deviceIDs": ["other"]}]},
    ],
)
async def test_invalid_edits_do_not_write(client, raw, changes):
    client._request.return_value = raw
    with pytest.raises(CommandError):
        await client.set_schedule("T6R-parent", changes, revision(raw))
    assert client._request.await_count == 1


async def test_hot_water_parent_route_body_and_readback(client):
    raw = {
        "timedSchedule": {
            "days": [
                {
                    "day": d,
                    "periods": [
                        {"startTime": "07:00:00", "dhwState": "On"},
                        {"startTime": "08:00:00", "dhwState": "Off"},
                    ],
                }
                for d in DAYS
            ]
        }
    }
    changes = {
        "Sunday": [{"time": "09:00", "state": "On"}, {"time": "10:00", "state": "Off"}]
    }
    saved = {
        "timedSchedule": {
            "days": merge_days(raw, changes, client.devices["T6R-parent"], True)
        }
    }
    client._request.side_effect = [raw, None, saved]
    result = await client.set_schedule(
        "T6R-parent", changes, revision(raw), hot_water=True
    )
    method, path, body = client._request.call_args_list[1].args
    assert method == "PUT" and path.endswith("/devices/T6R-parent/dhw/schedule")
    assert body == saved
    assert result["days"]["Sunday"][0] == {"time": "09:00:00", "state": "On"}


async def test_create_from_none_requires_week(client):
    raw = {"scheduleType": "None"}
    client._request.return_value = raw
    with pytest.raises(CommandError, match="all seven"):
        await client.set_schedule(
            "T6R-parent",
            {"Monday": [{"time": "08:00", "temperature": 20}]},
            revision(raw),
        )
    changes = {d: [{"time": "08:00", "temperature": 20}] for d in DAYS}
    saved = {
        "scheduleType": "Timed",
        "scheduleSubType": "EMEA",
        "timedSchedule": {
            "days": merge_days(raw, changes, client.devices["T6R-parent"], False)
        },
    }
    client._request.side_effect = [raw, None, saved]
    result = await client.set_schedule("T6R-parent", changes, revision(raw))
    assert len(result["days"]) == 7


async def test_does_not_overwrite_geofence(client, raw):
    raw["scheduleType"] = "Geofence"
    client._request.return_value = raw
    with pytest.raises(CommandError, match="Geofence"):
        await client.set_schedule("T6R-parent", {}, revision(raw))
    assert client._request.await_count == 1


async def test_write_timeout_is_not_replayed(client, raw):
    client._request.side_effect = [raw, CannotConnect("unknown delivery")]
    with pytest.raises(CannotConnect):
        await client.set_schedule(
            "T6R-parent",
            {"Monday": [{"time": "08:00", "temperature": 20}]},
            revision(raw),
        )
    assert client._request.await_count == 2


async def test_readback_mismatch_is_not_success(client, raw):
    client._request.side_effect = [raw, None, *[raw for _ in range(5)]]
    result = await client.set_schedule("T6R-parent", {"Monday": [{"time": "08:00", "temperature": 20}]}, revision(raw))
    assert result["status"] == "readback_unconfirmed"
    assert result["mismatched_days"] == ["Monday"]
    assert result["days"]["Monday"][0]["time"] == "06:30:00"
    assert client._request.await_count == 7


async def test_readback_failure_reports_accepted_write(client, raw):
    client._request.side_effect = [raw, None, *[CannotConnect("read failed") for _ in range(5)]]
    result = await client.set_schedule("T6R-parent", {"Monday": [{"time": "08:00", "temperature": 20}]}, revision(raw))
    assert result["status"] == "readback_unconfirmed"
    assert result["write_accepted"] is True
    assert "read failed" in result["readback_error"]
    assert client._request.await_count == 7


async def test_malformed_schedule_never_written(client):
    from custom_components.resideo_native.protocol.errors import InvalidResponse

    client._request.return_value = {
        "timedSchedule": {"days": [{"day": "Monday", "periods": "invalid"}]}
    }
    with pytest.raises(InvalidResponse):
        await client.set_schedule("T6R-parent", {}, "anything")
    assert client._request.await_count == 1


async def test_hot_water_create_full_week(client):
    raw = {"timedSchedule": None}
    changes = {d: [{"time": "00:00", "state": "Off"}] for d in DAYS}
    saved = {
        "timedSchedule": {
            "days": merge_days(raw, changes, client.devices["T6R-parent"], True)
        }
    }
    client._request.side_effect = [raw, None, saved]
    result = await client.set_schedule(
        "T6R-parent", changes, revision(raw), hot_water=True
    )
    assert len(result["days"]) == 7


async def test_fahrenheit_display_is_not_converted_twice(client, raw):
    d = client.devices["T6R-parent"]
    d.raw["thermostat"]["units"] = "Fahrenheit"
    result = merge_days(
        raw, {"Monday": [{"time": "08:00", "temperature": 68}]}, d, False
    )
    assert result[0]["periods"][0]["heatSetPoint"] == 68
    assert (
        present({"timedSchedule": {"days": result}}, d, False)["days"]["Monday"][0][
            "temperature"
        ]
        == 68
    )


@pytest.mark.parametrize('count', [1, 3, 4, 6])
def test_variable_period_counts_are_not_fixed_to_reporter(client, raw, count):
    changes = {'Monday': [{'time': f'{i * 3 + 1:02}:15', 'temperature': 18 + i / 2} for i in range(count)]}
    days = merge_days(raw, changes, client.devices['T6R-parent'], False)
    assert len(days[0]['periods']) == count
    assert days[1:] == raw['timedSchedule']['days'][1:]


async def test_unknown_response_is_not_empty_schedule(client):
    client._request.return_value = {'unexpected': 'private-value', 'deviceID': 'private-id'}
    result = await client.get_schedule('T6R-parent', hot_water=True)
    assert result['status'] == 'unrecognized_response'
    assert result['write_supported'] is False
    assert 'private' not in str(result)
    assert result['response_structure']['fields'] == {'deviceID': 'str'}
    assert client._request.await_count == 1


async def test_unrecognized_response_never_enables_creation(client):
    from custom_components.resideo_native.protocol.errors import InvalidResponse
    client._request.return_value = {'deviceID': 'private-id'}
    with pytest.raises(InvalidResponse, match='Structure:'):
        await client.set_schedule('T6R-parent', {d: [{'time': '08:00', 'temperature': 20}] for d in DAYS}, 'revision')
    assert client._request.await_count == 1


def test_jasper_edit_does_not_inject_cancellation_field(client, raw):
    for day in raw['timedSchedule']['days']:
        for p in day['periods']:
            p.pop('isCancelled')
    days = merge_days(raw, {'Monday': [{'time': '06:30', 'temperature': 19.5}]}, client.devices['T6R-parent'], False)
    period = days[0]['periods'][0]
    assert set(period) == {'startTime', 'periodType', 'heatSetPoint', 'coolSetPoint'}
    assert period['heatSetPoint'] == 67.1
    assert days[1:] == raw['timedSchedule']['days'][1:]


async def test_emea_write_omits_read_only_period_fields_on_all_days(client, raw):
    from copy import deepcopy
    original = deepcopy(raw)
    calls = []
    async def request(method, path, body=None):
        calls.append((method, path, body))
        if method == 'PUT':
            for day in body['timedSchedule']['days']:
                for period in day['periods']:
                    assert 'periodType' not in period
                    assert 'isCancelled' not in period
            return None
        if len(calls) == 1:
            return raw
        # Resideo may add read-only fields again in the GET response.
        result = deepcopy(raw)
        result['timedSchedule']['days'][0]['periods'][0]['heatSetPoint'] = 67.1
        return result
    client._request.side_effect = request
    changes = {'Monday': [{'time': '06:30', 'temperature': 19.5}, {'time': '22:30', 'temperature': 16}]}
    result = await client.set_schedule('T6R-parent', changes, revision(raw))
    assert result['days']['Monday'][0]['temperature'] == 19.5
    assert raw == original
    assert calls[1][2]['deviceIDs'] == ['T6R-parent']
