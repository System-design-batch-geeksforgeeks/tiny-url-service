from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

RESERVED_CODES = frozenset({"urls", "health", "favicon.ico"})

_ALIAS_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
_MAX_URL_LEN = 2048
_ALIAS_MIN = 3
_ALIAS_MAX = 32


def require_http_url(long_url: str) -> str:
    if not isinstance(long_url, str) or not long_url.strip():
        raise ValueError("long_url is required")
    url = long_url.strip()
    if len(url) > _MAX_URL_LEN:
        raise ValueError("long_url is too long")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("long_url must be an http or https URL")
    return url


def require_alias(alias: str) -> str:
    if not isinstance(alias, str) or not alias.strip():
        raise ValueError("custom_alias is empty")
    code = alias.strip()
    if len(code) < _ALIAS_MIN or len(code) > _ALIAS_MAX:
        raise ValueError(f"custom_alias must be {_ALIAS_MIN}-{_ALIAS_MAX} characters")
    if any(ch not in _ALIAS_CHARS for ch in code):
        raise ValueError("custom_alias may contain letters, digits, _ and - only")
    if code.lower() in RESERVED_CODES:
        raise ValueError("custom_alias is reserved")
    return code


def parse_expiration(value: str | None, now: datetime) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("expiration_date must be an ISO-8601 string")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        expires = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("expiration_date must be ISO-8601") from exc
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    expires = expires.astimezone(timezone.utc)
    if expires <= now:
        raise ValueError("expiration_date must be in the future")
    return expires
