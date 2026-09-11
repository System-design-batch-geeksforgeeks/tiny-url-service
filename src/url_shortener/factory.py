from __future__ import annotations

import os

from url_shortener.clock import Clock
from url_shortener.memory import BatchedCounter, InMemoryCounter, InMemoryUrlRepository, TtlCache
from url_shortener.service import UrlShortener


def build_memory_service(public_base: str = "http://127.0.0.1:8080", batch_size: int = 100) -> UrlShortener:
    allocator = InMemoryCounter(start=0)
    return UrlShortener(
        urls=InMemoryUrlRepository(),
        counter=BatchedCounter(allocator, batch_size=batch_size),
        cache=TtlCache(),
        clock=Clock(),
        public_base=public_base,
    )


def build_aws_service() -> UrlShortener:
    import boto3

    from url_shortener.aws_stores import DynamoBatchedCounter, DynamoCounterAllocator, DynamoUrlRepository

    dynamodb = boto3.resource("dynamodb")
    urls_table = dynamodb.Table(_require_env("URLS_TABLE"))
    counters_table = dynamodb.Table(_require_env("COUNTERS_TABLE"))
    batch_size = int(os.environ.get("COUNTER_BATCH_SIZE", "100"))
    allocator = DynamoCounterAllocator(counters_table)
    return UrlShortener(
        urls=DynamoUrlRepository(urls_table),
        counter=DynamoBatchedCounter(allocator, batch_size=batch_size),
        cache=TtlCache(),
        clock=Clock(),
        public_base=os.environ.get("PUBLIC_BASE_URL", "https://invalid.example"),
    )


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing environment variable {name}")
    return value
