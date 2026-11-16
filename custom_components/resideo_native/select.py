"""Explicit room-priority controls for FlyCatcher/T9/T10 thermostats."""

from __future__ import annotations

from itertools import combinations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ResideoCoordinator
from .protocol import Thermostat
from .protocol.rooms import ROOM_PRIORITY_HOLDS

_FOLLOW_ME_SETPOINTS = {
    "Heat": ("heat",),
    "EmergencyHeat": ("heat",),
    "Cool": ("cool",),
    "Auto": ("heat", "cool"),
    "AutoHeat": ("heat", "cool"),
    "AutoCool": ("heat", "cool"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ResideoCoordinator = entry.runtime_data
    seen: set[str] = set()

    @callback
    def add_selectors() -> None:
        added = []
        for device_id, device in (coordinator.data or {}).items():
            if device.supports_rooms and device.room_priority and device_id not in seen:
                seen.add(device_id)
                added.append(ResideoRoomPriority(coordinator, device_id))
        if added:
            async_add_entities(added)

    add_selectors()
    entry.async_on_unload(coordinator.async_add_listener(add_selectors))


class ResideoRoomPriority(CoordinatorEntity[ResideoCoordinator], SelectEntity):
    """Expose manual room selection and motion-based Follow Me."""

    _attr_has_entity_name = True
    _attr_name = "Room priority"
    _attr_icon = "mdi:home-thermometer-outline"

    def __init__(self, coordinator: ResideoCoordinator, device_id: str):
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"{device_id}_room_priority"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def device(self):
        return (self.coordinator.data or {}).get(self.device_id)

    @property
    def available(self) -> bool:
        device = self.device
        return bool(super().available and device and device.online and device.room_priority)

    # A native WholeHouse state can be read from the app, but its write
    # format remains unsupported on this legacy endpoint. Display it without
    # falsely claiming that PickARoom(all) is the same native mode.
    _APP_WHOLE_HOUSE = "Whole House (set in Resideo app)"

    def _choices(self) -> dict[str, tuple[str, list[int]]]:
        """Map All rooms to the proven PickARoom request with every room ID.

        Every available room is selected in a single cloud write. Up to six
        rooms get all combinations; larger sites retain All rooms and singles.
        """
        device = self.device
        priority = device.room_priority if device else None
        if not priority:
            return {}
        rooms = sorted((rid, name[:30]) for rid, name in priority.room_names)
        choices: dict[str, tuple[str, list[int]]] = {"Follow Me": ("FollowMe", [])}
        if rooms:
            choices["All rooms"] = ("PickARoom", [rid for rid, _ in rooms])
        for room_id, room_name in rooms:
            choices[f"Room: {room_name} (#{room_id})"] = ("PickARoom", [room_id])
        if 2 <= len(rooms) <= 6:
            for count in range(2, len(rooms)):
                for subset in combinations(rooms, count):
                    label = "Rooms: " + ", ".join(f"{name} (#{rid})" for rid, name in subset)
                    choices[label] = ("PickARoom", [rid for rid, _ in subset])
        return choices

    @property
    def options(self) -> list[str]:
        choices = list(self._choices())
        priority = self.device.room_priority if self.device else None
        if priority and priority.priority_type == "WholeHouse":
            choices.append(self._APP_WHOLE_HOUSE)
        if priority and priority.priority_type == "PickARoom":
            if not any(mode == "PickARoom" and set(ids) == set(priority.selected_rooms)
                       for mode, ids in self._choices().values()):
                choices.append("Multiple rooms (use Resideo app to edit)")
        return choices

    @property
    def current_option(self) -> str | None:
        priority = self.device.room_priority if self.device else None
        if not priority:
            return None
        if priority.priority_type == "WholeHouse":
            return self._APP_WHOLE_HOUSE
        if priority.priority_type == "FollowMe":
            return "Follow Me"
        if priority.priority_type == "PickARoom":
            for label, (mode, ids) in self._choices().items():
                if mode == "PickARoom" and set(ids) == set(priority.selected_rooms):
                    return label
            return "Multiple rooms (use Resideo app to edit)"
        return None

    async def async_select_option(self, option: str) -> None:
        # Read-only representations of app-reported priority modes and
        # combinations beyond six rooms must never send speculative writes.
        if option in (self._APP_WHOLE_HOUSE, "Multiple rooms (use Resideo app to edit)"):
            if self.current_option == option:
                return
            raise HomeAssistantError("This priority can only be set in the Resideo app")
        choices = self._choices()
        if not self.available or option not in choices:
            raise HomeAssistantError("Choose a supported FlyCatcher priority option")
        mode, ids = choices[option]

        def confirmed(data: dict[str, Thermostat]) -> bool:
            device = data.get(self.device_id)
            if (
                device is None
                or not device.online
                or (priority := device.room_priority) is None
                or priority.priority_type != mode
            ):
                return False
            if mode == "PickARoom":
                return set(priority.selected_rooms) == set(ids)
            if (
                device.schedule_enabled is not False
                and priority.hold_status not in ROOM_PRIORITY_HOLDS
                and device.values.get("thermostatSetpointStatus") not in ROOM_PRIORITY_HOLDS
            ):
                return False
            return all(
                device.setpoint(kind) is not None
                for kind in _FOLLOW_ME_SETPOINTS.get(device.mode or "", ())
            )

        await self.coordinator.async_command(
            self.coordinator.client.set_room_priority(self.device_id, mode, ids),
            confirmed=confirmed,
            read_back_key=f"room_priority:{self.device_id}",
            unconfirmed_warning=(
                "Resideo did not confirm the Follow Me room-priority change"
                if mode == "FollowMe" else None
            ),
        )

    @property
    def extra_state_attributes(self):
        priority = self.device.room_priority if self.device else None
        return {
            "selected_room_names": [
                name for rid, name in priority.room_names
                if rid in priority.selected_rooms
            ],
        } if priority else {}
