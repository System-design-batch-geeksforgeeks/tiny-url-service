"""API Gateway HTTP API (payload 2.0) entrypoints. Container reuse keeps the counter batch and cache."""

from __future__ import annotations

import base64

from url_shortener.factory import build_aws_service
from url_shortener.http_app import handle_http
from url_shortener.service import UrlShortener

_service: UrlShortener | None = None


def _service_singleton() -> UrlShortener:
    global _service
    if _service is None:
        _service = build_aws_service()
    return _service


def handle_write(event, _context):
    return _dispatch(event)


def handle_read(event, _context):
    return _dispatch(event)


def _dispatch(event: dict) -> dict:
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method") or "GET"
    path = event.get("rawPath") or http.get("path") or "/"
    path_params = event.get("pathParameters") or {}
    if "short_code" in path_params and method == "GET":
        path = f"/{path_params['short_code']}"
    body = _decode_body(event)
    public_base = _public_base(event)
    response = handle_http(_service_singleton(), method, path, body, public_base=public_base)
    return {
        "statusCode": response.status,
        "headers": response.header_map(),
        "body": response.body,
    }


def _decode_body(event: dict) -> str | None:
    body = event.get("body")
    if body is None:
        return None
    if event.get("isBase64Encoded"):
        return base64.b64decode(body).decode("utf-8")
    return body


def _public_base(event: dict) -> str:
    ctx = event.get("requestContext") or {}
    domain = ctx.get("domainName")
    if domain:
        return f"https://{domain}"
    return "https://invalid.example"
