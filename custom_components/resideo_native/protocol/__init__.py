"""Standalone Resideo native protocol; no Home Assistant imports."""

from .auth import ResideoAuth, Token
from .client import NativeClient
from .device import Thermostat, number
from .errors import (
    AuthenticationError,
    CannotConnect,
    CommandError,
    InteractionRequired,
    InvalidCallback,
    InvalidResponse,
    RateLimited,
    ResideoError,
)

__all__ = [
    "AuthenticationError",
    "CannotConnect",
    "CommandError",
    "InteractionRequired",
    "InvalidCallback",
    "InvalidResponse",
    "NativeClient",
    "RateLimited",
    "ResideoAuth",
    "ResideoError",
    "Thermostat",
    "Token",
    "number",
]
