"""Keep FlyCatcher room measurements and priority flags accessory-specific."""

import pytest

from custom_components.resideo_native.protocol.device_types import safe_number
from custom_components.resideo_native.protocol.rooms import parse_room_response


@pytest.mark.parametrize("trailing_items", ([], [None]), ids=("valid-list", "trailing-null"))
def test_each_accessory_supplies_its_own_exclusion_flags(trailing_items):
    payload = {
        "rooms": [{
            "id": 1,
            "accessories": [
                {
                    "accessoryId": "wireless-a",
                    "type": "IndoorAirSensor",
                    "excludeTemp": False,
                    "excludeMotion": True,
                    "accessoryValue": {},
                },
                {
                    "accessoryId": "wireless-b",
                    "type": "IndoorAirSensor",
                    "excludeTemp": True,
                    "excludeMotion": False,
                    "accessoryValue": {"excludeTemp": False},
                },
                *trailing_items,
            ],
        }],
    }

    accessories = parse_room_response(payload, group_id=0, convert_temperature=safe_number)
    assert set(accessories) == {"0:wireless-a", "0:wireless-b"}
    assert accessories["0:wireless-a"].exclude_temp is False
    assert accessories["0:wireless-a"].exclude_motion is True
    assert accessories["0:wireless-b"].exclude_temp is False
    assert accessories["0:wireless-b"].exclude_motion is False


@pytest.mark.parametrize("wrap_priority", (False, True), ids=("rooms", "priority"))
def test_missing_measurements_never_use_room_averages(wrap_priority):
    readings = {"status": "Ok"}
    rooms = {
        "rooms": [{
            "id": 1,
            "avgTemperature": 73,
            "avgHumidity": 36,
            "overallMotion": True,
            "accessories": [
                {
                    "accessoryId": "built-in",
                    "accessoryAttribute": {"type": "Thermostat"},
                    "accessoryValue": {"indoorTemperature": 76, "indoorHumidity": 42},
                },
                {
                    "accessoryId": "wireless-a",
                    "accessoryAttribute": {"type": "IndoorAirSensor"},
                    "accessoryValue": readings,
                },
            ],
        }],
    }
    payload = {"currentPriority": rooms} if wrap_priority else rooms

    accessories = parse_room_response(payload, group_id=0, convert_temperature=safe_number)
    assert set(accessories) == {"0:wireless-a"}
    sensor = accessories["0:wireless-a"]
    assert sensor.online
    assert (sensor.temperature, sensor.humidity, sensor.motion) == (None, None, None)

    readings.update(indoorTemperature=71, indoorHumidity=47, motionDet=False)
    accessories = parse_room_response(payload, group_id=0, convert_temperature=safe_number)
    sensor = accessories["0:wireless-a"]
    assert (sensor.temperature, sensor.humidity) == (71.0, 47.0)
    assert sensor.motion is False
