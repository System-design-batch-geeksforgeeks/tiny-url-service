from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import unquote

from url_shortener.errors import NotFound, UrlShortenerError
from url_shortener.models import ShortenCommand
from url_shortener.service import UrlShortener
from url_shortener.validation import RESERVED_CODES


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: str = ""
    headers: dict[str, str] | None = None

    def header_map(self) -> dict[str, str]:
        headers = dict(self.headers or {})
        if self.body and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        return headers


def handle_http(
    service: UrlShortener,
    method: str,
    path: str,
    body: str | None,
    public_base: str | None = None,
) -> HttpResponse:
    method = method.upper()
    path = unquote(path.split("?", 1)[0])
    trimmed = path.rstrip("/") or "/"

    try:
        if method == "GET" and trimmed == "/health":
            return _json_ok(200, {"ok": True})
        if method == "POST" and trimmed == "/urls":
            return _shorten(service, body, public_base)
        if method == "GET" and trimmed != "/":
            code = trimmed.lstrip("/")
            if "/" in code or code.lower() in RESERVED_CODES:
                raise NotFound("short code not found")
            return _redirect(service, code)
        return HttpResponse(
            404,
            json.dumps({"error": "not_found", "message": "no such route"}),
        )
    except UrlShortenerError as exc:
        return _json_error(exc)
    except ValueError as exc:
        return HttpResponse(
            400,
            json.dumps({"error": "bad_request", "message": str(exc)}),
        )


def _json_error(exc: UrlShortenerError) -> HttpResponse:
    return HttpResponse(exc.status_code, json.dumps({"error": exc.error_code, "message": exc.message}))


def _json_ok(status: int, payload: dict) -> HttpResponse:
    return HttpResponse(status, json.dumps(payload))


def _shorten(service: UrlShortener, body: str | None, public_base: str | None) -> HttpResponse:
    if not body or not body.strip():
        raise ValueError("JSON body is required")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("body must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("body must be a JSON object")
    result = service.shorten(
        ShortenCommand(
            long_url=payload.get("long_url"),
            custom_alias=payload.get("custom_alias"),
            expiration_date=payload.get("expiration_date"),
        )
    )
    short_url = result.short_url
    if public_base:
        short_url = f"{public_base.rstrip('/')}/{result.short_code}"
    return _json_ok(201, {"short_url": short_url, "short_code": result.short_code})


def _redirect(service: UrlShortener, short_code: str) -> HttpResponse:
    mapping = service.resolve(short_code)
    return HttpResponse(
        302,
        "",
        {
            "Location": mapping.long_url,
            "Cache-Control": "no-store",
        },
    )
