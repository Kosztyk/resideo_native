# Resideo Native v0.3.4 changed files

- `room_entity.py`, `sensor.py`, `binary_sensor.py` and `select.py` expose FlyCatcher accessories and room priority.
- `protocol/client.py`, `protocol/device.py`, `protocol/rooms.py`, `protocol/device_types.py` and `protocol/priority_validation.py` handle discovery, command serialization, target parsing and sanitized diagnostics.
- `coordinator.py` handles bounded room-priority readback. `diagnostics.py` includes room-sensor coverage and the active priority mode.
- `climate.py` supports Home Assistant’s native temperature API. `__init__.py` and `manifest.json` register the room platforms.
- `const.py`, the schedule editor JavaScript, packaging checks, test metadata and release workflow use the stable version.
- `README.md`, `START_HERE.md`, `CHANGELOG.md`, `VALIDATION.md`, `HACS_PUBLISHING.md`, `docs/SCHEDULES.md`, `docs/ROOM_SENSORS.md` and `RELEASE_NOTES_0.3.4.md` document the new features and release.
