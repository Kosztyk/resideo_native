# Jasper/T6R domestic hot water — mobile protocol evidence

Version 0.1.8 implements the legacy mobile API used by the supplied
**Resideo Smart Home Android 6.21.1** APK. It does not use the developer-key API
or the newer Titan/First Alert service.

APK SHA-256:

```text
3e5f5b2ae3e61ae0bd28693e69a4870ebe603dcc39f0038e7165d71fded44e87
```

## Reading

The existing authenticated `GET https://lyric.alarmnet.com/api/v4/locations`
returns thermostat devices. A thermostat may contain this nested zone:

```json
{
  "dhwZone": {
    "deviceId": "<zone identifier>",
    "deviceClass": "DHW",
    "deviceType": "DHW",
    "dhw": {
      "dhwState": "Off",
      "status": "NoHold",
      "boostDuration": 0,
      "vacationHold": {"enabled": false},
      "geoBoostEnabled": false,
      "nextPeriodTime": "17:00:00"
    },
    "currentSchedulePeriod": {"day": "Monday", "period": "P2"}
  }
}
```

The example is synthetic. Model references in the APK include
`com.honeywell.granite.restclient.common.HotWaterResponse`, `DhwResponse`,
and `diy.response.stat.StatDeviceResponse`. The app maps `mHotWaterResponse`
into its parent thermostat's DHW view model in `y9/w.l`.

The integration creates a water-heater entity and an enum state sensor only
when a valid nested zone is present. Their attributes whitelist the fields
above. It uses the existing account poll; it adds no per-zone polling endpoint.

## Command address: use the parent thermostat ID

All commands below use this prefix:

```text
https://lyric.alarmnet.com/api/v3/locations/{location_id}/devices/{thermostat_id}/dhw/
```

`thermostat_id` is the **parent device's `deviceID`**, not
`dhwZone.deviceId`. Both path identifiers are URL escaped. The existing
authenticated mobile-client headers are reused.

This distinction comes from the app's actual call chain:

- `y9/w.l` constructs the DHW view model `E9/a` from its parent thermostat.
- `m7/c.<init>(m7/c)` copies the parent's `q` device identifier and `E` location.
- `comfortsolution.presentation.view.DHWDeviceView.g` passes those parent
  identifiers into `boostHotWater` / `turnHotWaterOff`.
- The detail screen `ta/h.onCreate` loads the parent thermostat by `DEVICE_ID`;
  `ta/h.N3`, `ta/h.O3`, and `ta/h.onActivityResult` pass that ID and `LOCATION_ID`
  into the same command layer.

## Routes and bodies recovered from the app

Every request below is **PUT**, with JSON as shown. Path suffixes are appended
to the prefix above.

| Intent | Path suffix | JSON request body | APK evidence |
| --- | --- | --- | --- |
| Always on | `systemSwitch` | `{"systemSwitch":"Heat"}` | `ta/h.N3(true)` → `y9/u.H` → `Ce/c.Q0` |
| Always off | `systemSwitch` | `{"systemSwitch":"Off"}` | `ta/h.N3(false)` → `y9/u.H` → `Ce/c.Q0` |
| Follow/resume schedule | `scheduleStatus` | `{"scheduleStatus":"Resume"}` | `ta/h.onActivityResult` → `Ce/c.m` |
| Boost for 30 minutes | `state` | `{"dhwState":"On","boostTime":30}` | `DHWDeviceView.g` / `ta/h.O3` → `Ce/c.l` |
| Boost for 60 minutes | `state` | `{"dhwState":"On","boostTime":60}` | `I9/e.BOOST60` → `ta/h.O3` → `Ce/c.l` |
| Boost for 90 minutes | `state` | `{"dhwState":"On","boostTime":90}` | `I9/e.BOOST90` → `ta/h.O3` → `Ce/c.l` |
| Cancel boost / temporary off | `state` | `{"dhwState":"Off"}` | `DHWDeviceView.g` / `ta/h.O3` → `Ce/c.T0` |

In `Ce/c`, each method assembles `api/v3/locations/` + location + `/devices/` +
device + the corresponding DHW suffix, serializes the request object and uses
the `PUT` method. Request classes under
`com.honeywell.granite.restclient.hotWater.request` define these exact fields:

- `SystemSwitchRequest`: `systemSwitch`.
- `ChangeScheduleStatusRequest`: `scheduleStatus`.
- `BoostHotWaterRequest`: `dhwState`, `boostTime`.
- `OffHotwaterRequest`: `dhwState` only.

`I9/e` defines `BOOST30`, `BOOST60`, `BOOST90` with integer values 30, 60, 90.
The app's default dashboard boost is 30 minutes. The command field is
**`boostTime`**, whereas **`boostDuration`** is a reported status field.
Always-on uses **`Heat`**, while the boost state uses **`On`**.

Cancel and resume are separate commands. The integration does not assume that
`{"dhwState":"Off"}` has restored the schedule: the explicit resume action
uses `scheduleStatus` with `Resume` and reads the resulting state back.

## Home Assistant representation

| Reported status | Water-heater operation mode |
| --- | --- |
| `NoHold` | `auto`; read the separate state sensor to see whether DHW is currently on or off |
| `PermanentHold` + `On` / `Off` | `on` / `off` |
| `TemporaryHold` + `On` | `boost` |
| `TemporaryHold` + `Off` | `off`; the `status` attribute preserves that it is temporary |
| `VacationHold` or an unrecognized status | Unknown operation mode; retain reported status and DHW on/off sensor |

The user-facing `boost` mode starts 30 minutes. The
`resideo_native.boost_hot_water` action accepts a duration of 30, 60 or 90.
`water_heater.turn_off` means permanent off; use
`resideo_native.cancel_hot_water_boost` to send temporary off instead.

The API payload establishes neither a hot-water temperature measurement nor a
temperature target, so no water-temperature controls or measurements are
fabricated. No away-mode, vacation or geo-boost setting commands are implemented.
Those reported fields remain readable attributes. Heating/DHW schedule actions
and the visual editor added after 0.1.8 are documented in [SCHEDULES.md](SCHEDULES.md).

## Verification limits

The commands and parent addressing above were recovered from APK bytecode,
not guessed from the issue's field names. Local tests verify exact HTTP paths
and JSON bodies, invalid-command rejection, no replay of timed-out writes,
server readback, entity discovery/lifecycle, diagnostics redaction and Home
Assistant actions on **2026.10.2**.

The issue #2 requester confirmed state/attributes and the `on`, `off` and
`auto` commands against the Resideo app and physical Jasper/T6R thermostat on
Home Assistant 2026.10.4. The 0.3.1 report additionally confirms a boost started
from HA and ran normally, auto/off changes and DHW schedule edit/clear/restore.
The boost duration was not specified; individual durations and explicit boost
cancellation were not separately confirmed. See
[the hardware evidence](TESTING_2026-10-27.md). The maintainer has no DHW hardware.
Writes are enabled only for the legacy `Jasper` model;
other compatible nested-zone payloads remain readable without write features.

After installing and restarting, the tester can first compare the DHW state
sensor and attributes with the official app. Then test a 30-minute boost,
cancel, resume schedule, and explicit permanent modes as appropriate, checking
the result in the app and after a poll. Rejected commands surface as errors;
the integration never invents a successful state before server readback.
