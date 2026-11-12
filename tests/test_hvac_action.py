"""Regression coverage for Resideo operationStatus → Home Assistant hvac_action.

These tests are intended for the repository's Home Assistant test environment.
Copy to <repository>/tests/ when merging the patch upstream.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")
from homeassistant.components.climate import HVACAction, HVACMode

try:
    from custom_components.resideo_native.climate import ResideoThermostat
except ModuleNotFoundError:
    from resideo_native.climate import ResideoThermostat


@pytest.mark.parametrize(
    ("operation", "hvac_mode", "expected"),
    [
        ("EquipmentOff", HVACMode.HEAT, HVACAction.IDLE),
        ("EquipmentOff", HVACMode.COOL, HVACAction.IDLE),
        (" equipmentoff ", HVACMode.HEAT, HVACAction.IDLE),
        ("Heat", HVACMode.HEAT, HVACAction.HEATING),
        ("Heating", HVACMode.HEAT, HVACAction.HEATING),
        ("Cool", HVACMode.COOL, HVACAction.COOLING),
        ("Cooling", HVACMode.COOL, HVACAction.COOLING),
        ("Fan", HVACMode.HEAT, HVACAction.FAN),
        ("Idle", HVACMode.HEAT, HVACAction.IDLE),
        ("Off", HVACMode.HEAT, HVACAction.IDLE),
        ("None", HVACMode.HEAT, HVACAction.IDLE),
        (None, HVACMode.HEAT, None),
        ("UnknownFromCloud", HVACMode.HEAT, None),
        ("EquipmentOff", HVACMode.OFF, HVACAction.OFF),
        ("Heat", HVACMode.OFF, HVACAction.OFF),
        (None, HVACMode.OFF, HVACAction.OFF),
    ],
)
def test_operation_status_mapping(operation, hvac_mode, expected):
    entity = SimpleNamespace(
        device=SimpleNamespace(operation=operation),
        hvac_mode=hvac_mode,
    )
    assert ResideoThermostat.hvac_action.fget(entity) == expected


def test_unavailable_thermostat_has_no_action():
    assert ResideoThermostat.hvac_action.fget(SimpleNamespace(device=None)) is None
