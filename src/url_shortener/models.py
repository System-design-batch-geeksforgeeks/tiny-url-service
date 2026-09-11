from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class UrlMapping:
    short_code: str
    long_url: str
    created_at: datetime
    expires_at: datetime | None
    is_custom: bool

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and now >= self.expires_at


@dataclass(frozen=True, slots=True)
class ShortenCommand:
    long_url: str
    custom_alias: str | None = None
    expiration_date: str | None = None


@dataclass(frozen=True, slots=True)
class ShortenResult:
    short_code: str
    short_url: str
