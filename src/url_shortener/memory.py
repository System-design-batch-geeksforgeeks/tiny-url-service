from __future__ import annotations

import threading
import time

from url_shortener.models import UrlMapping


class InMemoryUrlRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[str, UrlMapping] = {}

    def put_if_absent(self, mapping: UrlMapping) -> bool:
        with self._lock:
            if mapping.short_code in self._rows:
                return False
            self._rows[mapping.short_code] = mapping
            return True

    def get(self, short_code: str) -> UrlMapping | None:
        with self._lock:
            return self._rows.get(short_code)


class InMemoryCounter:
    """Monotonic counter. Tests can start at 0; production wraps this with batching."""

    def __init__(self, start: int = 0) -> None:
        self._lock = threading.Lock()
        self._next = start

    def next_id(self) -> int:
        with self._lock:
            value = self._next
            self._next += 1
            return value

    def allocate(self, n: int) -> int:
        """Return the start of a half-open range [start, start+n)."""
        with self._lock:
            start = self._next
            self._next += n
            return start


class BatchedCounter:
    """Check out a range of ids from a backing allocator (Redis INCR / DynamoDB ADD)."""

    def __init__(self, allocator: InMemoryCounter, batch_size: int = 100) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self._allocator = allocator
        self._batch_size = batch_size
        self._lock = threading.Lock()
        self._next = 0
        self._end = 0

    def next_id(self) -> int:
        with self._lock:
            if self._next >= self._end:
                start = self._allocator.allocate(self._batch_size)
                self._next = start
                self._end = start + self._batch_size
            value = self._next
            self._next += 1
            return value


class TtlCache:
    def __init__(self, max_items: int = 1024) -> None:
        self._max_items = max_items
        self._lock = threading.Lock()
        self._items: dict[str, tuple[UrlMapping, float]] = {}

    def get(self, short_code: str) -> UrlMapping | None:
        now = time.monotonic()
        with self._lock:
            hit = self._items.get(short_code)
            if hit is None:
                return None
            mapping, expires_at = hit
            if now >= expires_at:
                del self._items[short_code]
                return None
            return mapping

    def put(self, mapping: UrlMapping, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        expires_at = time.monotonic() + ttl_seconds
        with self._lock:
            if len(self._items) >= self._max_items:
                self._items.pop(next(iter(self._items)))
            self._items[mapping.short_code] = (mapping, expires_at)
