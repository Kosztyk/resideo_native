"""Bounded, redacted server validation details for schedule failures only."""
import json
import re


def schedule_validation_detail(text, secrets=()):
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        return 'No JSON validation detail returned'
    if not isinstance(payload, dict):
        return 'No structured validation detail returned'
    allowed = {'message', 'code', 'errorcode', 'error_description', 'title', 'detail',
               'errors', 'modelstate', 'error'}
    parts = []
    def collect(value, depth=0):
        if depth > 3 or len(parts) >= 8:
            return
        if isinstance(value, str):
            parts.append(value[:600])
        elif isinstance(value, (int, float)):
            parts.append(str(value))
        elif isinstance(value, list):
            for child in value[:8]:
                collect(child, depth + 1)
        elif isinstance(value, dict):
            for key, child in list(value.items())[:16]:
                # Validation-map keys may contain submitted identifiers. Keep
                # message values only; exclude stack traces and arbitrary fields.
                if str(key).casefold() not in {'stacktrace', 'exception', 'trace', 'innerexception'}:
                    collect(child, depth + 1)
    for key, value in payload.items():
        if str(key).casefold() in allowed:
            collect(value)
    detail = '; '.join(parts) or 'No recognized validation message returned'
    for secret in sorted({str(s) for s in secrets if s is not None and len(str(s)) >= 3}, key=len, reverse=True):
        detail = detail.replace(secret, '[redacted]')
    detail = re.sub(r'(?i)Bearer\s+\S+', 'Bearer [redacted]', detail)
    detail = re.sub(r'https?://\S+', '[redacted URL]', detail)
    detail = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[redacted email]', detail)
    detail = re.sub(r'\b[A-Za-z0-9_-]{32,}(?:\.[A-Za-z0-9_-]+)*\b', '[redacted identifier]', detail)
    detail = re.sub(r'\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b', '[redacted identifier]', detail)
    return detail[:1200].replace('\n', ' ').replace('\r', ' ')
