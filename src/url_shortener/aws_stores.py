from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from url_shortener.errors import Unavailable
from url_shortener.models import UrlMapping

try:
    from botocore.exceptions import ClientError
except ImportError:  # local tests without boto3
    ClientError = Exception  # type: ignore[misc, assignment]


def _epoch(dt: datetime) -> int:
    return int(dt.astimezone(timezone.utc).timestamp())


def mapping_to_item(mapping: UrlMapping) -> dict:
    item: dict = {
        "short_code": mapping.short_code,
        "long_url": mapping.long_url,
        "created_at": Decimal(_epoch(mapping.created_at)),
        "is_custom": mapping.is_custom,
    }
    if mapping.expires_at is not None:
        exp = _epoch(mapping.expires_at)
        item["expires_at"] = Decimal(exp)
        item["ttl"] = Decimal(exp)
    return item


def item_to_mapping(item: dict) -> UrlMapping:
    expires = item.get("expires_at")
    return UrlMapping(
        short_code=item["short_code"],
        long_url=item["long_url"],
        created_at=datetime.fromtimestamp(int(item["created_at"]), tz=timezone.utc),
        expires_at=None if expires is None else datetime.fromtimestamp(int(expires), tz=timezone.utc),
        is_custom=bool(item.get("is_custom", False)),
    )


class DynamoUrlRepository:
    def __init__(self, table) -> None:
        self._table = table

    def put_if_absent(self, mapping: UrlMapping) -> bool:
        try:
            self._table.put_item(
                Item=mapping_to_item(mapping),
                ConditionExpression="attribute_not_exists(short_code)",
            )
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code == "ConditionalCheckFailedException":
                return False
            raise Unavailable("could not persist short URL") from exc

    def get(self, short_code: str) -> UrlMapping | None:
        try:
            resp = self._table.get_item(Key={"short_code": short_code}, ConsistentRead=True)
        except ClientError as exc:
            raise Unavailable("could not read short URL") from exc
        item = resp.get("Item")
        if item is None:
            return None
        return item_to_mapping(item)


class DynamoCounterAllocator:
    """Atomic ADD on a single item — the DynamoDB equivalent of Redis INCR."""

    def __init__(self, table, counter_id: str = "global") -> None:
        self._table = table
        self._counter_id = counter_id

    def allocate(self, n: int) -> int:
        try:
            resp = self._table.update_item(
                Key={"counter_id": self._counter_id},
                UpdateExpression="ADD current_value :n",
                ExpressionAttributeValues={":n": Decimal(n)},
                ReturnValues="UPDATED_NEW",
            )
        except ClientError as exc:
            raise Unavailable("could not allocate short-code ids") from exc
        new_value = int(resp["Attributes"]["current_value"])
        return new_value - n


@dataclass
class DynamoBatchedCounter:
    allocator: DynamoCounterAllocator
    batch_size: int = 100
    _next: int = field(default=0, init=False, repr=False)
    _end: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        import threading

        self._lock = threading.Lock()

    def next_id(self) -> int:
        with self._lock:
            if self._next >= self._end:
                start = self.allocator.allocate(self.batch_size)
                self._next = start
                self._end = start + self.batch_size
            value = self._next
            self._next += 1
            return value
