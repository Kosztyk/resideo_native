"""Safe, deliberately body-free exceptions for the native Resideo protocol."""


class ResideoError(Exception):
    """Base protocol exception. Never include credentials or response bodies."""


class AuthenticationError(ResideoError):
    """Credentials or refresh authorization were rejected."""


class InvalidCallback(AuthenticationError):
    """A malformed or mismatched callback was rejected before token exchange."""


class InteractionRequired(AuthenticationError):
    """Complete sign-in, verification, or agreement acceptance in a browser."""


class CannotConnect(ResideoError):
    """Connection failed, timed out, or returned an unexpected response."""


class InvalidResponse(ResideoError):
    """The API response does not match the protocol recovered from the app."""


class RateLimited(ResideoError):
    """The service requested a pause."""

    def __init__(self, retry_after: float = 60) -> None:
        self.retry_after = max(1.0, retry_after)
        super().__init__("Resideo temporarily limited requests; retry later")


class CommandError(ResideoError):
    """The device cannot safely perform the requested command."""
