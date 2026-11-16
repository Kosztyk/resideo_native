"""Primitive validation reused by thermostat and wireless-room parsing."""

from __future__ import annotations

from math import isfinite
from typing import Any


def safe_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return parsed if isfinite(parsed) else None
