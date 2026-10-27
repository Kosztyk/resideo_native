"""Bounded read-only verification of eventually consistent schedule writes."""

import asyncio

from .errors import ResideoError

# Retry GET only. A write is never repeated when delivery/readback is uncertain.
READBACK_DELAYS = (0, 1, 2, 4, 8)


async def verify_readback(read, matches):
    """Return the last observation and confirmation, without inventing success."""
    last = None
    error = None
    for attempt, delay in enumerate(READBACK_DELAYS, 1):
        if delay:
            await asyncio.sleep(delay)
        try:
            last = await read()
            if matches(last):
                return last, True, attempt, None
            error = None
        except ResideoError as err:
            error = str(err)
    return last, False, attempt, error


def verification_result(actual, verified, attempts, error=None):
    """Expose uncertain readback as response data, not a fake server rejection."""
    result = dict(actual or {})
    result.update(write_accepted=True, verification_attempts=attempts)
    if verified:
        result["verification_status"] = "verified"
    else:
        result.update(
            status="readback_unconfirmed",
            verification_status="unconfirmed",
            message=(
                "Resideo accepted the write, but the requested result was not "
                "confirmed within the verification window. The returned days/status "
                "are the last observed cloud values. Check the app and reload before "
                "retrying; no write was replayed."
            ),
        )
        if error:
            result["readback_error"] = error
    return result
