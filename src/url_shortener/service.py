from __future__ import annotations

from url_shortener.clock import Clock
from url_shortener.encoding import code_from_counter
from url_shortener.errors import Conflict, Gone, NotFound
from url_shortener.models import ShortenCommand, ShortenResult, UrlMapping
from url_shortener.stores import Cache, Counter, UrlRepository
from url_shortener.validation import parse_expiration, require_alias, require_http_url

_CACHE_CEILING_SECONDS = 300
_GENERATED_RETRIES = 5


class UrlShortener:
    def __init__(
        self,
        urls: UrlRepository,
        counter: Counter,
        cache: Cache,
        clock: Clock | None = None,
        public_base: str = "http://127.0.0.1:8080",
    ) -> None:
        self._urls = urls
        self._counter = counter
        self._cache = cache
        self._clock = clock or Clock()
        self._public_base = public_base.rstrip("/")

    def shorten(self, command: ShortenCommand) -> ShortenResult:
        now = self._clock.now()
        long_url = require_http_url(command.long_url)
        expires_at = parse_expiration(command.expiration_date, now)
        is_custom = command.custom_alias is not None
        alias = require_alias(command.custom_alias) if is_custom else None

        for _ in range(_GENERATED_RETRIES):
            short_code = alias if alias is not None else code_from_counter(self._counter.next_id())
            mapping = UrlMapping(
                short_code=short_code,
                long_url=long_url,
                created_at=now,
                expires_at=expires_at,
                is_custom=is_custom,
            )
            if self._urls.put_if_absent(mapping):
                self._cache.put(mapping, self._ttl_seconds(mapping, now))
                return ShortenResult(
                    short_code=short_code,
                    short_url=f"{self._public_base}/{short_code}",
                )
            if is_custom:
                raise Conflict("custom_alias already in use")
        raise Conflict("could not allocate a unique short code")

    def resolve(self, short_code: str) -> UrlMapping:
        if not short_code:
            raise NotFound("short code not found")
        now = self._clock.now()
        mapping = self._cache.get(short_code)
        if mapping is None:
            mapping = self._urls.get(short_code)
            if mapping is None:
                raise NotFound("short code not found")
            self._cache.put(mapping, self._ttl_seconds(mapping, now))
        if mapping.is_expired(now):
            raise Gone("short URL has expired")
        return mapping

    def _ttl_seconds(self, mapping: UrlMapping, now) -> int:
        if mapping.expires_at is None:
            return _CACHE_CEILING_SECONDS
        remaining = int((mapping.expires_at - now).total_seconds())
        return max(0, min(_CACHE_CEILING_SECONDS, remaining))
