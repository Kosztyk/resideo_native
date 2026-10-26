"""Synthetic two-thermostat account matching the structure in issue #2."""

from copy import deepcopy

from test_protocol import locations


def dhw_locations():
    payload = locations()
    device = deepcopy(payload[0]["devices"][1])
    device["deviceID"] = "T6R-parent"
    device["name"] = "Second thermostat"
    device["dhwZone"] = {
        "deviceId": "DHW-zone-not-the-command-address",
        "deviceClass": "DHW",
        "deviceType": "DHW",
        "dhw": {
            "dhwState": "Off",
            "status": "NoHold",
            "boostDuration": 0,
            "vacationHold": {"enabled": False},
            "geoBoostEnabled": False,
            "nextPeriodTime": "17:00:00",
        },
        "currentSchedulePeriod": {"day": "Monday", "period": "P2"},
    }
    payload[0]["devices"].append(device)
    return payload
