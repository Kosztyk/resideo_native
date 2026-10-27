"""Native status must resume independently of timed-period edit validation."""

from copy import deepcopy

import pytest

from custom_components.resideo_native.protocol.device import parse_locations
from custom_components.resideo_native.protocol.errors import CannotConnect
from custom_components.resideo_native.protocol.schedules import revision
from dhw_fixtures import dhw_locations
from test_schedules import client, raw


@pytest.mark.parametrize("source_kind", ["sparse", "inactive", "inactive_without_periods"])
async def test_resume_sends_only_native_status_and_refreshes_restored_routine(client, raw, source_kind):
    source = deepcopy(raw)
    for day in source["timedSchedule"]["days"]:
        if day["day"] != "Friday":
            day["periods"] = []
    if source_kind != "sparse":
        source["scheduleType"] = "None"
    if source_kind == "inactive_without_periods":
        source = {"scheduleType": "None"}
    locations = dhw_locations()
    parent = next(d for d in locations[0]["devices"] if d.get("deviceID") == "T6R-parent")
    parent["scheduleStatus"] = "Pause"
    client.devices = parse_locations(deepcopy(locations))
    parent["scheduleStatus"] = "Resume"
    client._request.side_effect = [source, None, locations, raw]
    result = await client.set_schedule_enabled("T6R-parent", True, revision(source))
    put = client._request.call_args_list[1]
    assert put.args == ("PUT", "api/v2/locations/123/Schedule/Status", {"a": 123, "DeviceIds": ["T6R-parent"], "ScheduleStatus": "Resume"})
    assert sum(c.args[0] == "PUT" for c in client._request.call_args_list) == 1
    assert all("/hold" not in c.args[1] and "/ThermostatSchedule" not in c.args[1] for c in client._request.call_args_list)
    assert result["schedule_enabled"] is True
    assert result["verification_status"] == "verified"
    assert result["schedule_content_refreshed"] is True
    assert result["schedule_type"] == "Timed"
    assert result["revision"] == revision(raw)
    assert result["days"]["Monday"][0]["temperature"] == 19


async def test_status_success_is_not_rejected_when_routine_refresh_fails(client, raw):
    locations = dhw_locations()
    parent = next(d for d in locations[0]["devices"] if d.get("deviceID") == "T6R-parent")
    parent["scheduleStatus"] = "Resume"
    client._request.side_effect = [raw, None, locations, CannotConnect("read failed")]
    result = await client.set_schedule_enabled("T6R-parent", True, revision(raw))
    assert result["schedule_enabled"] is True
    assert result["verification_status"] == "verified"
    assert result["verification_scope"] == "native_schedule_status"
    assert result["schedule_content_refreshed"] is False
    assert result["write_supported"] is False
    assert "Load from Resideo" in result["message"]
