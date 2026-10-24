# Resideo Native v0.1.7 — HACS physical-device testing clarification

Responds to [HACS review #12444](https://github.com/hacs/default/pull/12444).

- Maintainer confirms using a real **Jasper** thermostat through Resideo
  Native and observing acceptance of HVAC mode, target temperature and
  hold/preset commands on the physical thermostat.
- README and VALIDATION.md now document the actual tested model and the
  device registry's lack of firmware version information (`sw_version: null`).
- Clearly distinguish this first-hand report from broader untested model/
  firmware combinations and from offline CI.
- Remove obsolete declarations that no real-device command test occurred.

**All runtime write paths are preserved unchanged.** No thermostat commands,
network protocol, security, climate, or automation behavior changed.
