"""Read-only FlyCatcher/T9/T10 wireless room accessory models.

Shapes come from Resideo Android 6.21.2's ComfortRoom/AccessoryValue
classes and the legacy priority endpoint. No API write operation is defined.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .device_types import safe_number
from .errors import InvalidResponse

ROOM_PRIORITY_HOLDS = ("TemporaryHold", "PermanentHold", "HoldUntil", "VacationHold")


@dataclass(slots=True)
class RoomAccessory:
    """A wireless sensor, identified independently of its room assignment."""

    key: str
    accessory_id: str
    group_id: int
    room_id: str
    room_name: str
    name: str
    model: str
    temperature: float | None
    humidity: float | None
    motion: bool | None
    occupancy: bool | None
    battery_status: str | None
    rssi: int | None
    status: str | None
    exclude_temp: bool | None
    exclude_motion: bool | None

    @property
    def online(self) -> bool:
        return (self.status or "").strip().casefold() not in {
            "offline", "disconnected", "unavailable", "lost", "notconnected",
            "not_connected", "not connected",
        }


def _id(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and value >= 0:
        return str(value)
    if isinstance(value, str) and value.strip() and len(value.strip()) <= 96:
        return value.strip()
    return None


def _value_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()[:128]
    return None


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _humidity(value: Any) -> float | None:
    n = safe_number(value)
    return n if n is not None and 0 <= n <= 100 else None


def _rssi(value: Any) -> int | None:
    n = safe_number(value)
    # RSSI is in dBm; 0 can indicate no radio sample, so omit it.
    return int(n) if n is not None and n != 0 and -200 <= n <= 0 else None


def discover_group_ids(raw: dict[str, Any]) -> tuple[int, ...]:
    """Use explicit group identifiers when provided, otherwise the app's group 0.

    Do not scan arbitrary group IDs or make requests against unrelated devices.
    """
    ids: set[int] = set()
    thermostat = raw.get("thermostat")
    containers = (raw, thermostat if isinstance(thermostat, dict) else {})
    for container in containers:
        for field in ("groupId", "groupID", "comfortGroupId"):
            val = container.get(field)
            if type(val) is int and 0 <= val <= 65535:
                ids.add(val)
        for field in ("groups", "comfortGroups", "roomGroups"):
            groups = container.get(field)
            if not isinstance(groups, list):
                continue
            for group in groups:
                if not isinstance(group, dict):
                    continue
                val = group.get("groupId", group.get("groupID", group.get("id")))
                if type(val) is int and 0 <= val <= 65535:
                    ids.add(val)
    return tuple(sorted(ids)) if ids else (0,)


def parse_room_response(
    payload: Any, *, group_id: int, convert_temperature: Callable[[Any], float | None]
) -> dict[str, RoomAccessory]:
    """Interpret native /group/{id}/rooms and /priority responses.

    Room averages are used only when an individual room contains exactly one
    wireless accessory; they are never misattributed to multiple accessories.
    """
    if isinstance(payload, dict):
        root = payload.get("currentPriority")
        if not isinstance(root, dict):
            root = payload
        rooms = root.get("rooms")
    elif isinstance(payload, list):
        rooms = payload
    else:
        raise InvalidResponse("Invalid FlyCatcher room response")
    if not isinstance(rooms, list):
        raise InvalidResponse("FlyCatcher room response has no rooms list")
    result: dict[str, RoomAccessory] = {}
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_id = _id(room.get("id", room.get("roomId")))
        if room_id is None:
            continue
        room_name = _value_str(room.get("name")) or _value_str(room.get("roomName")) or f"Room {room_id}"
        accessories = room.get("accessories")
        if not isinstance(accessories, list):
            continue
        remote = []
        for accessory in accessories:
            if not isinstance(accessory, dict):
                continue
            attrs = accessory.get("accessoryAttribute")
            values = accessory.get("accessoryValue")
            attrs = attrs if isinstance(attrs, dict) else {}
            values = values if isinstance(values, dict) else accessory
            sensor_type = (_value_str(attrs.get("type")) or _value_str(accessory.get("type")) or "").casefold()
            # Ignore the thermostat's built-in sensor. A type-less accessory
            # is accepted only if it has a remote accessory value structure.
            if sensor_type == "thermostat" or (sensor_type and sensor_type != "indoorairsensor"):
                continue
            if not sensor_type and not attrs and not isinstance(accessory.get("accessoryValue"), dict):
                continue
            accessory_id = _id(accessory.get("accessoryId", accessory.get("id")))
            if accessory_id is None:
                continue
            remote.append((accessory_id, attrs, values))
        for accessory_id, attrs, values in remote:
            temperature = convert_temperature(values.get("indoorTemperature", values.get("temperature")))
            humidity = _humidity(values.get("indoorHumidity"))
            if len(remote) == 1:
                if temperature is None:
                    temperature = convert_temperature(room.get("avgTemperature", room.get("roomAvgTemp")))
                if humidity is None:
                    humidity = _humidity(room.get("avgHumidity", room.get("roomAvgHumidity")))
            motion = _as_bool(values.get("motionDet", values.get("detectMotion")))
            if motion is None and len(remote) == 1:
                motion = _as_bool(room.get("overallMotion"))
            occupancy = _as_bool(values.get("occupancyDet"))
            battery = _value_str(values.get("batteryStatus")) or _value_str(attrs.get("batteryStatus"))
            status = _value_str(values.get("status")) or _value_str(attrs.get("status"))
            rssi = _rssi(values.get("rssiAverage", attrs.get("rssiAverage")))
            key = f"{group_id}:{accessory_id}"
            result[key] = RoomAccessory(
                key=key, accessory_id=accessory_id, group_id=group_id,
                room_id=room_id, room_name=room_name,
                name=_value_str(attrs.get("name")) or f"{room_name} Indoor Air Sensor",
                model=_value_str(attrs.get("model")) or "Honeywell Smart Room Sensor",
                temperature=temperature, humidity=humidity,
                motion=motion, occupancy=occupancy, battery_status=battery,
                rssi=rssi, status=status,
                exclude_temp=_as_bool(values.get("excludeTemp", accessory.get("excludeTemp"))),
                exclude_motion=_as_bool(values.get("excludeMotion", accessory.get("excludeMotion"))),
            )
    return result


@dataclass(slots=True, frozen=True)
class RoomPriority:
    """The current native room-priority selection, not an inferred schedule."""

    priority_type: str
    selected_rooms: tuple[int, ...]
    room_names: tuple[tuple[int, str], ...]
    hold_status: str | None = None
    hold_until: str | None = None


def parse_room_priority(payload: Any) -> RoomPriority | None:
    """Parse the APK's /priority response; reject unrecognized modes."""
    if not isinstance(payload, dict):
        return None
    priority = payload.get("currentPriority")
    if not isinstance(priority, dict):
        return None
    mode = priority.get("priorityType")
    if mode not in ("WholeHouse", "FollowMe", "PickARoom"):
        return None
    raw_selected = priority.get("selectedRooms")
    raw_rooms = priority.get("rooms")
    if not isinstance(raw_rooms, list):
        return None
    if raw_selected is None and mode in ("FollowMe", "WholeHouse"):
        raw_selected = []
    if not isinstance(raw_selected, list):
        return None
    selected = []
    names = []
    for item in raw_rooms:
        if not isinstance(item, dict):
            continue
        rid = item.get("id")
        if type(rid) is int and 0 <= rid <= 999:
            name = _value_str(item.get("roomName")) or _value_str(item.get("name")) or f"Room {rid}"
            names.append((rid, name))
    room_ids = {rid for rid, _ in names}
    for rid in raw_selected:
        if type(rid) is not int or rid not in room_ids or rid in selected:
            return None
        selected.append(rid)
    if mode == "PickARoom" and not selected:
        return None
    # The /priority endpoint reports its own hold status. It need not
    # match thermostat.changeableValues. Preserve *only* recognized enums.
    status = payload.get("status")
    if not isinstance(status, str) or status not in ("NoHold", *ROOM_PRIORITY_HOLDS):
        status = None
    until = payload.get("holdUntil")
    if not isinstance(until, str) or not until.strip():
        until = None
    return RoomPriority(mode, tuple(selected), tuple(names), status, until)
