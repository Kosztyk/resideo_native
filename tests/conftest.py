"""Use the official custom-integration harness for Home Assistant tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))


@pytest.fixture(autouse=True)
def protocol_loopback_server(request):
    """The protocol suite uses a localhost server, not external services."""
    if request.node.path.name in ("test_protocol.py", "test_hot_water_protocol.py"):
        request.getfixturevalue("socket_enabled")


@pytest.fixture(autouse=True)
def quick_schedule_readbacks(monkeypatch):
    # Exercise all verification attempts without waiting on wall-clock delays.
    monkeypatch.setattr("custom_components.resideo_native.protocol.schedule_readback.READBACK_DELAYS", (0, 0, 0, 0, 0))
