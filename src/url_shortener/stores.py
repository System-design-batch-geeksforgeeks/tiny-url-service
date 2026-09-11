from __future__ import annotations

from typing import Protocol

from url_shortener.models import UrlMapping


class UrlRepository(Protocol):
    def put_if_absent(self, mapping: UrlMapping) -> bool:
        """Return True if inserted, False if short_code already exists."""

    def get(self, short_code: str) -> UrlMapping | None: ...


class Counter(Protocol):
    def next_id(self) -> int: ...


class Cache(Protocol):
    def get(self, short_code: str) -> UrlMapping | None: ...

    def put(self, mapping: UrlMapping, ttl_seconds: int) -> None: ...
