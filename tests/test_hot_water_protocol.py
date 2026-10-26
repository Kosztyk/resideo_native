"""DHW parsing and actual HTTP requests to a local simulated Resideo server."""

from __future__ import annotations

import json
import sys
import time
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components/resideo_native"))

from protocol import CannotConnect, CommandError, NativeClient, ResideoAuth, Token
from protocol import client as client_module
from protocol.device import parse_locations

from dhw_fixtures import dhw_locations


class HotWaterProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.payload = dhw_locations()
        self.writes = []
        self.failure = None
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self.handle)
        self.server = TestServer(app, host="127.0.0.1")
        await self.server.start_server()
        self.base_patch = patch.object(
            client_module, "BASE_URL", str(self.server.make_url("/"))
        )
        self.base_patch.start()
        self.session = aiohttp.ClientSession()
        auth = ResideoAuth(
            self.session, Token("test-access", "test-refresh", time.time() + 3600)
        )
        self.client = NativeClient(self.session, auth)
        await self.client.update()

    async def asyncTearDown(self):
        await self.session.close()
        await self.server.close()
        self.base_patch.stop()

    async def handle(self, request):
        if request.method == "GET" and request.path == "/api/v2/session":
            return web.json_response({"user": {"userID": 456}})
        if request.method == "GET" and request.path == "/api/v4/locations":
            return web.json_response(self.payload)
        body = await request.json()
        self.writes.append((request.method, request.raw_path, body))
        if self.failure:
            return web.json_response(
                {"private": "must-not-appear-in-errors"}, status=self.failure
            )
        return web.Response(status=204)

    def test_nested_zone_does_not_replace_or_duplicate_thermostats(self):
        self.assertEqual(set(self.client.devices), {"T6-test", "T6R-parent"})
        self.assertIsNone(self.client.devices["T6-test"].hot_water)
        zone = self.client.devices["T6R-parent"].hot_water
        self.assertEqual(zone.state, "Off")
        self.assertEqual(zone.operation_mode, "auto")
        self.assertTrue(zone.can_control)
        self.assertEqual(
            zone.attributes,
            {
                "dhw_state": "Off",
                "status": "NoHold",
                "boost_duration": 0,
                "vacation_hold_enabled": False,
                "geo_boost_enabled": False,
                "next_period_time": "17:00:00",
                "schedule_day": "Monday",
                "schedule_period": "P2",
            },
        )
        self.assertEqual(self.writes, [])

    def test_statuses_preserve_schedule_state_distinction(self):
        zone = self.client.devices["T6R-parent"].hot_water
        for status, state, expected in (
            ("NoHold", "Off", "auto"),
            ("NoHold", "On", "auto"),
            ("PermanentHold", "Off", "off"),
            ("PermanentHold", "On", "on"),
            ("TemporaryHold", "On", "boost"),
            ("TemporaryHold", "Off", "off"),
            ("VacationHold", "Off", None),
            ("NewStatus", "On", None),
        ):
            with self.subTest(status=status, state=state):
                zone.values.update(status=status, dhwState=state)
                self.assertEqual(zone.operation_mode, expected)
                self.assertEqual(zone.state, state)

    def test_unknown_state_is_unknown_and_optional_fields_are_tolerant(self):
        zone = self.client.devices["T6R-parent"].hot_water
        zone.values.update(
            dhwState="Unsupported",
            status="Future",
            boostDuration=True,
            vacationHold=[],
            geoBoostEnabled="false",
            nextPeriodTime={},
        )
        zone.raw["currentSchedulePeriod"] = []
        self.assertIsNone(zone.state)
        self.assertIsNone(zone.operation_mode)
        for key in (
            "boost_duration",
            "vacation_hold_enabled",
            "geo_boost_enabled",
            "next_period_time",
            "schedule_day",
            "schedule_period",
        ):
            self.assertIsNone(zone.attributes[key])

    def test_missing_or_malformed_zone_is_ignored(self):
        device = self.client.devices["T6R-parent"]
        for invalid in (
            None,
            [],
            {},
            {"deviceId": "zone", "dhw": []},
            {"deviceId": "", "dhw": {}},
            {"deviceId": 5, "dhw": {}},
            {"deviceId": "zone", "dhw": {}, "deviceClass": "Other"},
        ):
            with self.subTest(zone=invalid):
                device.raw["dhwZone"] = invalid
                self.assertIsNone(device.hot_water)

    async def test_mode_requests_use_parent_id_and_exact_app_bodies(self):
        expected = (
            ("on", "systemSwitch", {"systemSwitch": "Heat"}),
            ("off", "systemSwitch", {"systemSwitch": "Off"}),
            ("auto", "scheduleStatus", {"scheduleStatus": "Resume"}),
        )
        for mode, suffix, body in expected:
            await self.client.set_hot_water_mode("T6R-parent", mode)
            self.assertEqual(
                self.writes[-1],
                (
                    "PUT",
                    f"/api/v3/locations/123/devices/T6R-parent/dhw/{suffix}",
                    body,
                ),
            )
        self.assertEqual(len(self.writes), 3)
        self.assertNotIn("DHW-zone-not-the-command-address", json.dumps(self.writes))

    async def test_all_boost_durations_and_default(self):
        for minutes in (30, 60, 90):
            await self.client.boost_hot_water("T6R-parent", minutes)
            self.assertEqual(
                self.writes[-1],
                (
                    "PUT",
                    "/api/v3/locations/123/devices/T6R-parent/dhw/state",
                    {"dhwState": "On", "boostTime": minutes},
                ),
            )
        await self.client.boost_hot_water("T6R-parent")
        self.assertEqual(self.writes[-1][2]["boostTime"], 30)

    async def test_cancel_boost_is_distinct_from_permanent_off(self):
        await self.client.cancel_hot_water_boost("T6R-parent")
        self.assertEqual(
            self.writes,
            [
                (
                    "PUT",
                    "/api/v3/locations/123/devices/T6R-parent/dhw/state",
                    {"dhwState": "Off"},
                )
            ],
        )

    async def test_invalid_modes_and_durations_send_nothing(self):
        for mode in ("Heat", "boost", "cool", None):
            with self.subTest(mode=mode), self.assertRaises(CommandError):
                await self.client.set_hot_water_mode("T6R-parent", mode)
        for duration in (True, 0, -30, 15, 31, 120, 30.5, 30.0, "30", None):
            with self.subTest(duration=duration), self.assertRaises(CommandError):
                await self.client.boost_hot_water("T6R-parent", duration)
        self.assertEqual(self.writes, [])

    async def test_missing_offline_and_other_model_devices_send_nothing(self):
        for device_id in ("missing", "T6-test"):
            with self.assertRaises(CommandError):
                await self.client.set_hot_water_mode(device_id, "on")
        device = self.client.devices["T6R-parent"]
        for level, key, value in (
            ("parent", "isAlive", False),
            ("zone", "isAlive", False),
            ("parent", "deviceType", "Titan"),
        ):
            original = deepcopy(device.raw)
            target = device.raw if level == "parent" else device.raw["dhwZone"]
            target[key] = value
            for command in (
                self.client.set_hot_water_mode("T6R-parent", "on"),
                self.client.boost_hot_water("T6R-parent"),
                self.client.cancel_hot_water_boost("T6R-parent"),
            ):
                with self.assertRaises(CommandError):
                    await command
            device.raw.clear()
            device.raw.update(original)
        self.assertEqual(self.writes, [])

    async def test_failed_write_does_not_update_state_and_is_not_retried(self):
        self.failure = 400
        with self.assertRaises(CommandError) as error:
            await self.client.boost_hot_water("T6R-parent")
        self.assertNotIn("must-not-appear", str(error.exception))
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.client.devices["T6R-parent"].hot_water.state, "Off")

    async def test_timed_out_write_is_not_replayed(self):
        with patch.object(self.session, "request", side_effect=TimeoutError) as request:
            with self.assertRaises(CannotConnect):
                await self.client.boost_hot_water("T6R-parent")
        self.assertEqual(request.call_count, 1)
        self.assertEqual(self.client.devices["T6R-parent"].hot_water.state, "Off")

    async def test_readback_is_the_only_source_of_new_state(self):
        await self.client.boost_hot_water("T6R-parent")
        self.assertEqual(
            self.client.devices["T6R-parent"].hot_water.operation_mode, "auto"
        )
        raw = self.payload[0]["devices"][2]["dhwZone"]["dhw"]
        raw.update(dhwState="On", status="TemporaryHold", boostDuration=30)
        await self.client.update()
        self.assertEqual(
            self.client.devices["T6R-parent"].hot_water.operation_mode, "boost"
        )
        self.assertEqual(self.client.devices["T6-test"].setpoint("heat"), 22)

    async def test_command_path_escapes_parent_identifiers(self):
        device = self.client.devices.pop("T6R-parent")
        device.device_id = "parent/with space"
        device.location_id = "location/1"
        self.client.devices[device.device_id] = device
        await self.client.boost_hot_water(device.device_id)
        self.assertEqual(
            self.writes[-1][1],
            "/api/v3/locations/location%2F1/devices/parent%2Fwith%20space/dhw/state",
        )
