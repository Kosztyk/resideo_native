"""Classify FlyCatcher priority HTTP errors without disclosing server text.

Only finite, hardcoded categories are returned; response values, tokens, IDs,
room names, account information, and URLs must never reach a log entry.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FIELDS = (
    ("selected_rooms", re.compile(r"(?i)\bselected[._ -]?rooms\b")),
    ("hold_until", re.compile(r"(?i)\bhold[._ -]?until\b")),
    ("priority_type", re.compile(r"(?i)\bpriority[._ -]?type\b")),
    ("hold_status", re.compile(r"(?i)\bhold[._ -]?status\b")),
    ("priority", re.compile(r"(?i)\bpriority\b")),
    ("status", re.compile(r"(?i)\bstatus\b")),
    ("type", re.compile(r"(?i)\btype\b")),
)
_REASONS = (
    ("null_not_allowed", re.compile(r"(?i)\b(?:null|non-null|not\s+null)\b")),
    ("missing_or_required", re.compile(r"(?i)\b(?:missing|required|must\s+be\s+provided)\b")),
    ("unsupported", re.compile(r"(?i)\b(?:unsupported|not\s+supported|not\s+allowed)\b")),
    ("invalid", re.compile(r"(?i)\b(?:invalid|incorrect|malformed|not\s+valid)\b")),
    ("conflict", re.compile(r"(?i)\b(?:conflict|already|locked)\b")),
)
_KEYS = frozenset({"message", "detail", "title", "errors", "error", "errorcode", "code", "errordescription", "validationerrors", "modelstate", "details"})


def priority_error_evidence(response_text: str | None) -> tuple[str, str, str]:
    """Return (body_format, reason_hint, field_hint), never server-controlled text.

    A hint indicates that a key phrase appeared in the error response; it is
    not a verified explanation of the rejection. Interpret conservatively.
    """
    if not response_text or not response_text.strip():
        return ("empty", "unknown", "none")
    try:
        parsed: Any = json.loads(response_text[:16384])
    except (ValueError, TypeError):
        return ("non_json", "unknown", "none")
    if not isinstance(parsed, dict):
        return ("json_other", "unknown", "none")
    fragments: list[str] = []

    def walk(value: Any, depth: int) -> None:
        if depth > 3 or len(fragments) >= 12:
            return
        if isinstance(value, dict):
            for key, val in list(value.items())[:12]:
                if len(fragments) >= 12:
                    break
                # Only the syntax of known error fields is inspected.
                key_str = str(key)
                if key_str.casefold().replace('_','').replace('-','') in _KEYS:
                    walk(val, depth + 1)
                elif depth > 0 and isinstance(val, (str, list)):
                    # Field names in validation maps sometimes appear as keys.
                    fragments.append(key_str[:96]); walk(val, depth + 1)
        elif isinstance(value, (list, tuple)):
            for val in value[:8]:
                walk(val, depth + 1)
        elif isinstance(value, str):
            fragments.append(value[:512])

    walk(parsed, 0)
    if not fragments:
        return ("json", "unknown", "none")
    evidence = " ".join(fragments)[:1500].replace("_", " ")
    field = next((label for label, pattern in _FIELDS if pattern.search(evidence)), "none")
    reason = next((label for label, pattern in _REASONS if pattern.search(evidence)), "unknown")
    return ("json", reason, field)
