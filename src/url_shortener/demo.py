"""Scripted HLD walkthrough against the local (or any) HTTP API."""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.request
import urllib.response
from http.server import ThreadingHTTPServer

from url_shortener.factory import build_memory_service
from url_shortener.server import make_handler


class _NoFollowRedirects(urllib.request.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        result = urllib.response.addinfourl(fp, headers, req.get_full_url())
        result.status = code
        result.code = code
        return result

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


class _PassThroughErrors(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response

    https_response = http_response


_OPENER = urllib.request.build_opener(_NoFollowRedirects, _PassThroughErrors)


def _request(base: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict, str]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    with _OPENER.open(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        parsed = json.loads(raw) if raw else {}
        status = getattr(resp, "status", None) or resp.getcode()
        location = resp.headers.get("Location") or ""
        return int(status), parsed, location


def _step(title: str) -> None:
    print(f"\n==> {title}")


def run_hld_script(base: str) -> None:
    print("=== URL shortener — high-level design demo ===")
    print(f"API: {base}")

    health_status, health, _ = _request(base, "GET", "/health")
    assert health_status == 200 and health.get("ok") is True, health
    print("health: ok")

    _step("1. Create a short URL (write service → counter → urls table)")
    status, created, _ = _request(
        base,
        "POST",
        "/urls",
        {"long_url": "https://www.example.com/some/very/long/url"},
    )
    assert status == 201, (status, created)
    code = created["short_code"]
    print(f"POST /urls → 201 short_code={code} short_url={created['short_url']}")

    _step("2. Redirect with 302 (read service; not 301 so we keep control)")
    status, _, location = _request(base, "GET", f"/{code}")
    assert status == 302, status
    assert location == "https://www.example.com/some/very/long/url", location
    print(f"GET /{code} → 302 Location: {location}")

    _step("3. Optional custom alias")
    status, alias, _ = _request(
        base,
        "POST",
        "/urls",
        {
            "long_url": "https://hellointerview.com/learn/system-design/problem-breakdowns/bitly",
            "custom_alias": "my-talk",
        },
    )
    assert status == 201, (status, alias)
    print(f"POST /urls alias=my-talk → {alias['short_url']}")
    status, _, location = _request(base, "GET", "/my-talk")
    assert status == 302 and "hellointerview.com" in location, (status, location)
    print(f"GET /my-talk → 302 Location: {location}")

    _step("4. Duplicate alias is rejected (conditional put)")
    status, err, _ = _request(
        base,
        "POST",
        "/urls",
        {"long_url": "https://example.com/other", "custom_alias": "my-talk"},
    )
    assert status == 409, (status, err)
    print(f"POST /urls alias=my-talk again → 409 {err}")

    _step("5. Expiration → 410 Gone (cache TTL ≤ remaining life)")
    status, expiring, _ = _request(
        base,
        "POST",
        "/urls",
        {
            "long_url": "https://example.com/expires",
            "custom_alias": "temp-link",
            "expiration_date": _rfc3339_seconds_from_now(8),
        },
    )
    assert status == 201, (status, expiring)
    status, _, location = _request(base, "GET", "/temp-link")
    assert status == 302, (status, location)
    print("GET /temp-link immediately → 302")
    print("waiting for expiry...")
    gone = {}
    deadline = time.monotonic() + 20
    status = 302
    while time.monotonic() < deadline:
        time.sleep(0.5)
        status, gone, _ = _request(base, "GET", "/temp-link")
        if status == 410:
            break
    assert status == 410, (status, gone)
    print(f"GET /temp-link after expiry → 410 {gone}")

    _step("6. Unknown code → 404")
    status, missing, _ = _request(base, "GET", "/does-not-exist")
    assert status == 404, (status, missing)
    print(f"GET /does-not-exist → 404 {missing}")

    _step("7. Generated codes are unique")
    status, a, _ = _request(base, "POST", "/urls", {"long_url": "https://example.com/a"})
    status2, b, _ = _request(base, "POST", "/urls", {"long_url": "https://example.com/b"})
    assert status == 201 and status2 == 201
    assert a["short_code"] != b["short_code"]
    print(f"codes {a['short_code']} and {b['short_code']} are distinct")

    print("\nHLD demo passed.")


def _rfc3339_seconds_from_now(seconds: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        run_hld_script(argv[0].rstrip("/"))
        return 0

    host = "127.0.0.1"
    box: dict[str, str] = {"base": "http://127.0.0.1"}
    service = build_memory_service(public_base="http://127.0.0.1")
    httpd = ThreadingHTTPServer((host, 0), make_handler(service, lambda: box["base"], quiet=True))
    public_base = f"http://{host}:{httpd.server_address[1]}"
    box["base"] = public_base
    service._public_base = public_base
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        run_hld_script(public_base)
    finally:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
