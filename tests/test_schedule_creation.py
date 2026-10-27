"""Creation and explicitly confirmed geofence conversion, using synthetic accounts."""

from copy import deepcopy

import pytest

from custom_components.resideo_native.protocol.errors import CommandError
from custom_components.resideo_native.protocol.schedules import DAYS, revision
from test_schedules import client, raw


def full_week(hot=False):
    return {
        d: (
            [{"time": "07:10", "state": "On"}, {"time": "08:20", "state": "Off"}]
            if hot
            else [
                {"time": "07:15", "temperature": 19.5},
                {"time": "22:15", "temperature": 16},
            ]
        )
        for d in DAYS
    }


async def test_get_geofence_without_timed_data_is_recognized(client):
    client._request.return_value = {
        "scheduleType": "Geofence",
        "geoFenceSchedule": {"private": "not exposed"},
    }
    result = await client.get_schedule("T6R-parent")
    assert result["requires_conversion"] is True
    assert result["requires_full_week"] is True
    assert result["write_supported"] is True
    assert result["days"] == {}
    assert "private" not in str(result)
    assert client._request.await_count == 1


@pytest.mark.parametrize(
    "confirmation,days",
    [(False, full_week()), (True, {"Monday": full_week()["Monday"]})],
)
async def test_conversion_requires_consent_and_full_week(client, confirmation, days):
    source = {"scheduleType": "Geofence", "geoFenceSchedule": {}}
    client._request.return_value = source
    with pytest.raises(CommandError):
        await client.set_schedule(
            "T6R-parent", days, revision(source), confirm_conversion=confirmation
        )
    assert client._request.await_count == 1


async def test_geofence_conversion_uses_selected_parent_and_emea_schema(client):
    source = {
        "scheduleType": "Geofence",
        "geoFenceSchedule": {"homePeriod": {}},
        "timedSchedule": {
            "days": [
                {
                    "day": "Monday",
                    "periods": [{"startTime": "01:00", "heatSetPoint": 95}],
                }
            ]
        },
    }
    before = deepcopy(source)
    body_seen = None

    async def request(method, path, body=None):
        nonlocal body_seen
        if method == "PUT":
            body_seen = body
            assert body["deviceIDs"] == ["T6R-parent"]
            assert body["scheduleType"] == "Timed"
            assert body["scheduleSubType"] == "EMEA"
            assert "geoFenceSchedule" not in body
            for day in body["timedSchedule"]["days"]:
                for p in day["periods"]:
                    assert p["coolSetPoint"] == 0
                    assert not {"periodType", "isCancelled"} & set(p)
            return None
        if body_seen is None:
            return source
        return {k: v for k, v in body_seen.items() if k != "deviceIDs"}

    client._request.side_effect = request
    result = await client.set_schedule(
        "T6R-parent", full_week(), revision(source), confirm_conversion=True
    )
    assert result["schedule_type"] == "Timed"
    assert result["requires_conversion"] is False
    assert result["days"]["Monday"][0] == {"time": "07:15:00", "temperature": 19.5}
    assert source == before
    assert client._request.await_count == 3


async def test_empty_days_cannot_be_partially_created(client):
    source = {
        "scheduleType": "None",
        "timedSchedule": {"days": [{"day": d, "periods": []} for d in DAYS]},
    }
    client._request.return_value = source
    with pytest.raises(CommandError, match="all seven"):
        await client.set_schedule(
            "T6R-parent", {"Monday": full_week()["Monday"]}, revision(source)
        )
    assert client._request.await_count == 1


@pytest.mark.parametrize("hot", [False, True])
async def test_first_time_creation_roundtrips_complete_week(client, hot):
    source = {"timedSchedule": None} if hot else {"scheduleType": "None"}
    sent = None

    async def request(method, path, body=None):
        nonlocal sent
        if method == "PUT":
            sent = body
            assert len(body["timedSchedule"]["days"]) == 7
            assert (
                path.endswith("/dhw/schedule")
                if hot
                else path.endswith("/ThermostatSchedule")
            )
            return None
        return source if sent is None else sent

    client._request.side_effect = request
    result = await client.set_schedule(
        "T6R-parent", full_week(hot), revision(source), hot_water=hot
    )
    assert len(result["days"]) == 7
    assert result["requires_full_week"] is False
    assert client._request.await_count == 3


async def test_conversion_rejects_stale_revision_even_with_consent(client):
    client._request.return_value = {"scheduleType": "Geofence", "geoFenceSchedule": {}}
    with pytest.raises(CommandError, match="changed"):
        await client.set_schedule(
            "T6R-parent", full_week(), "stale", confirm_conversion=True
        )
    assert client._request.await_count == 1
