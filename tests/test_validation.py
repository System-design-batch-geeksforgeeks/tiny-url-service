from datetime import datetime, timedelta, timezone

import pytest

from url_shortener.validation import parse_expiration, require_alias, require_http_url


def test_http_url_ok():
    assert require_http_url("https://example.com/a") == "https://example.com/a"


def test_rejects_javascript():
    with pytest.raises(ValueError):
        require_http_url("javascript:alert(1)")


def test_rejects_empty_url():
    with pytest.raises(ValueError):
        require_http_url("  ")


def test_alias_charset():
    assert require_alias("my-talk") == "my-talk"
    with pytest.raises(ValueError):
        require_alias("ab")
    with pytest.raises(ValueError):
        require_alias("has space")
    with pytest.raises(ValueError):
        require_alias("health")


def test_expiration_must_be_future():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    future = parse_expiration("2026-06-01T00:00:00Z", now)
    assert future == datetime(2026, 6, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        parse_expiration("2025-01-01T00:00:00Z", now)
    assert parse_expiration(None, now) is None


def test_expiration_naive_is_utc():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    parsed = parse_expiration("2026-01-02T00:00:00", now)
    assert parsed.tzinfo is not None
    assert parsed > now
    assert now + timedelta(days=1) == parsed
