"""EMEA period lists and untouched empty days must survive partial edits."""

from copy import deepcopy

import pytest

from custom_components.resideo_native.protocol.errors import CommandError
from custom_components.resideo_native.protocol.schedules import DAYS, present, revision
from test_schedules import client, raw


async def test_emea_cancellation_metadata_does_not_remove_native_periods(client, raw):
    for day in raw["timedSchedule"]["days"]:
        for p in day["periods"]:
            p["isCancelled"] = True
    client._request.return_value = raw
    result = await client.get_schedule("T6R-parent")
    assert all(len(result["days"][d["day"]]) == 2 for d in raw["timedSchedule"]["days"])
    assert result["requires_full_week"] is False


async def test_emea_writer_preserves_native_periods_but_omits_na_fields(client, raw):
    for p in raw["timedSchedule"]["days"][1]["periods"]:
        p["isCancelled"] = True
    before = deepcopy(raw)
    sent = None

    async def request(method, path, body=None):
        nonlocal sent
        if method == "PUT":
            sent = body
            for day in body["timedSchedule"]["days"]:
                for p in day["periods"]:
                    assert not {"isCancelled", "periodType"} & set(p)
            return None
        return raw if sent is None else sent

    client._request.side_effect = request
    result = await client.set_schedule(
        "T6R-parent", {"Monday": [{"time": "08:00", "temperature": 20}]}, revision(raw)
    )
    assert len(sent["timedSchedule"]["days"][1]["periods"]) == 2
    assert len(result["days"]["Tuesday"]) == 2
    assert raw == before


async def test_untouched_empty_day_preserved_without_inventing_periods(client, raw):
    raw["timedSchedule"]["days"][1]["periods"] = []
    before = deepcopy(raw)
    sent = None

    async def request(method, path, body=None):
        nonlocal sent
        if method == "PUT":
            sent = body
            assert (
                body["timedSchedule"]["days"][1] == before["timedSchedule"]["days"][1]
            )
            return None
        return raw if sent is None else sent

    client._request.side_effect = request
    result = await client.set_schedule(
        "T6R-parent", {"Monday": [{"time": "08:00", "temperature": 20}]}, revision(raw)
    )
    assert result["days"]["Tuesday"] == []
    assert raw == before


@pytest.mark.parametrize("hot", [False, True])
async def test_clearing_last_period_preserves_empty_and_active_other_days(client, raw, hot):
    # The reported editor case has just Monday and Thursday populated.
    # Keep the native weekday objects and target one parent device only.
    if hot:
        raw = {"timedSchedule": {"days": [
            {"day": d, "periods": [{"startTime": "08:00:00", "dhwState": "Off"}]
             if d in ("Monday", "Thursday") else []}
            for d in DAYS
        ]}}
    else:
        for day in raw["timedSchedule"]["days"]:
            day["periods"] = day["periods"][:1] if day["day"] in ("Monday", "Thursday", "Sunday") else []
    before = deepcopy(raw)
    saved = deepcopy(raw)
    saved["timedSchedule"]["days"][0]["periods"] = []
    client._request.side_effect = [raw, None, saved]
    result = await client.set_schedule("T6R-parent", {"Monday": []}, revision(raw), hot_water=hot)
    method, path, body = client._request.call_args_list[1].args
    assert method == "PUT"
    assert path.endswith("/devices/T6R-parent/dhw/schedule" if hot else "/ThermostatSchedule")
    assert body["timedSchedule"]["days"][0] == {"day": "Monday", "periods": []}
    assert result["days"]["Monday"] == []
    assert result["days"]["Tuesday"] == []
    assert len(result["days"]["Thursday"]) == 1
    assert result["requires_full_week"] is False
    expected = deepcopy(before["timedSchedule"]["days"][1:])
    if not hot:
        assert body["deviceIDs"] == ["T6R-parent"]
        for day in expected:
            for period in day["periods"]:
                period.pop("periodType", None)
                period.pop("isCancelled", None)
    assert body["timedSchedule"]["days"][1:] == expected
    assert client._request.await_count == 3
    assert raw == before


async def test_deleting_one_period_preserves_remaining_heating_entries(client, raw):
    saved = deepcopy(raw)
    saved["timedSchedule"]["days"][0]["periods"] = raw["timedSchedule"]["days"][0]["periods"][1:]
    client._request.side_effect = [raw, None, saved]
    result = await client.set_schedule("T6R-parent", {"Monday": [{"time": "22:30", "temperature": 16}]}, revision(raw))
    sent = client._request.call_args_list[1].args[2]
    assert sent["timedSchedule"]["days"][0]["periods"] == [{"startTime": "22:30:00", "heatSetPoint": 60.8, "coolSetPoint": 0}]
    assert result["days"]["Monday"] == [{"time": "22:30:00", "temperature": 16}]


async def test_failed_deletion_readback_never_reports_success_or_replays_write(client, raw):
    client._request.side_effect = [raw, None, *[raw for _ in range(5)]]
    result = await client.set_schedule("T6R-parent", {"Monday": []}, revision(raw))
    assert result["status"] == "readback_unconfirmed"
    assert result["requested_days"]["Monday"] == []
    assert client._request.await_count == 7
    assert sum(c.args[0] == "PUT" for c in client._request.call_args_list) == 1


async def test_empty_day_deletion_still_checks_cloud_revision_before_put(client, raw):
    client._request.return_value = raw
    with pytest.raises(CommandError, match="changed.*no write was sent"):
        await client.set_schedule("T6R-parent", {"Monday": []}, "stale-revision")
    assert client._request.await_count == 1


@pytest.mark.parametrize("include_days", [False, True])
async def test_existing_empty_timed_week_requires_both_day_groups(client, include_days):
    source = {
        "scheduleType": "Timed",
        "scheduleSubType": "EMEA",
        "timedSchedule": {
            "days": [{"day": d, "periods": []} for d in DAYS] if include_days else []
        },
    }
    saved = deepcopy(source)
    saved["timedSchedule"]["days"] = [
        {"day": "Monday", "periods": [{"startTime": "08:00:00", "heatSetPoint": 68, "coolSetPoint": 0}]},
        *[{"day": d, "periods": [{"startTime": "09:00:00", "heatSetPoint": 66.2, "coolSetPoint": 0}] if d == "Saturday" else []} for d in DAYS[1:]],
    ]
    assert present(source, client.devices["T6R-parent"], False)["requires_full_week"] is False
    client._request.side_effect = [source, None, saved]
    result = await client.set_schedule(
        "T6R-parent", {"Monday": [{"time": "08:00", "temperature": 20}], "Saturday": [{"time": "09:00", "temperature": 19}]}, revision(source)
    )
    assert result["days"]["Monday"] == [{"time": "08:00:00", "temperature": 20}]
    assert result["requires_full_week"] is False
    assert client._request.call_args_list[1].args[2]["deviceIDs"] == ["T6R-parent"]


@pytest.mark.parametrize("deleted", ["Monday", "Saturday"])
async def test_cannot_delete_the_last_active_day_in_either_group(client, raw, deleted):
    for day in raw["timedSchedule"]["days"]:
        day["periods"] = day["periods"][:1] if day["day"] in ("Monday", "Saturday") else []
    client._request.return_value = raw
    with pytest.raises(CommandError, match="weekday.*weekend.*no write was sent"):
        await client.set_schedule("T6R-parent", {deleted: []}, revision(raw))
    assert client._request.await_count == 1


@pytest.mark.parametrize("hot", [False, True])
async def test_first_creation_still_requires_nonempty_days(client, hot):
    source = {"timedSchedule": None} if hot else {"scheduleType": "None"}
    client._request.return_value = source
    with pytest.raises(CommandError, match="Monday.*1–6.*no write was sent" if hot else "weekday.*weekend.*no write was sent"):
        await client.set_schedule("T6R-parent", {d: [] for d in DAYS}, revision(source), hot_water=hot)
    assert client._request.await_count == 1


async def test_first_creation_still_rejects_missing_days_without_put(client):
    raw = {"scheduleType": "None"}
    client._request.return_value = raw
    with pytest.raises(CommandError, match="all seven.*no write was sent"):
        await client.set_schedule(
            "T6R-parent",
            {"Monday": [{"time": "08:00", "temperature": 20}]},
            revision(raw),
        )
    assert client._request.await_count == 1


def test_na_reading_keeps_separate_cancellation_semantics(client, raw):
    raw["scheduleSubType"] = "NA"
    raw["timedSchedule"]["days"][0]["periods"][0]["isCancelled"] = True
    result = present(raw, client.devices["T6R-parent"], False)
    assert len(result["days"]["Monday"]) == 1
