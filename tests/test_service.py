from datetime import datetime, timedelta, timezone

import pytest

from url_shortener.clock import FrozenClock
from url_shortener.errors import Conflict, Gone, NotFound
from url_shortener.factory import build_memory_service
from url_shortener.memory import BatchedCounter, InMemoryCounter
from url_shortener.models import ShortenCommand


def test_shorten_and_resolve():
    svc = build_memory_service()
    result = svc.shorten(ShortenCommand(long_url="https://example.com/long"))
    mapping = svc.resolve(result.short_code)
    assert mapping.long_url == "https://example.com/long"
    assert result.short_url.endswith("/" + result.short_code)


def test_custom_alias_conflict():
    svc = build_memory_service()
    svc.shorten(ShortenCommand(long_url="https://example.com/a", custom_alias="my-talk"))
    with pytest.raises(Conflict):
        svc.shorten(ShortenCommand(long_url="https://example.com/b", custom_alias="my-talk"))


def test_same_long_url_gets_two_codes():
    svc = build_memory_service()
    a = svc.shorten(ShortenCommand(long_url="https://example.com/same"))
    b = svc.shorten(ShortenCommand(long_url="https://example.com/same"))
    assert a.short_code != b.short_code


def test_unknown_code():
    svc = build_memory_service()
    with pytest.raises(NotFound):
        svc.resolve("missing")


def test_expiration_410():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    clock = FrozenClock(start)
    svc = build_memory_service()
    svc._clock = clock
    svc.shorten(
        ShortenCommand(
            long_url="https://example.com/e",
            custom_alias="temp",
            expiration_date="2026-01-01T00:00:05Z",
        )
    )
    assert svc.resolve("temp").long_url.endswith("/e")
    svc._clock = FrozenClock(start + timedelta(seconds=6))
    with pytest.raises(Gone):
        svc.resolve("temp")


def test_counter_batching_is_unique_and_contiguous():
    allocator = InMemoryCounter(start=0)
    c1 = BatchedCounter(allocator, batch_size=10)
    c2 = BatchedCounter(allocator, batch_size=10)
    ids = [c1.next_id() for _ in range(10)] + [c2.next_id() for _ in range(10)]
    assert ids == list(range(20))
    assert len(set(ids)) == 20
