from datetime import datetime, timezone

from url_shortener.aws_stores import item_to_mapping, mapping_to_item
from url_shortener.models import UrlMapping


def test_item_round_trip():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    expires = datetime(2026, 2, 1, tzinfo=timezone.utc)
    mapping = UrlMapping(
        short_code="abc123",
        long_url="https://example.com/z",
        created_at=created,
        expires_at=expires,
        is_custom=True,
    )
    again = item_to_mapping(mapping_to_item(mapping))
    assert again.short_code == mapping.short_code
    assert again.long_url == mapping.long_url
    assert again.is_custom is True
    assert again.created_at == created
    assert again.expires_at == expires
    assert "ttl" in mapping_to_item(mapping)
