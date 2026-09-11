import json

from url_shortener.factory import build_memory_service
from url_shortener.http_app import handle_http


def test_create_and_redirect():
    svc = build_memory_service(public_base="http://short.test")
    created = handle_http(
        svc,
        "POST",
        "/urls",
        json.dumps({"long_url": "https://example.com/x"}),
        public_base="http://short.test",
    )
    assert created.status == 201
    code = json.loads(created.body)["short_code"]
    assert json.loads(created.body)["short_url"] == f"http://short.test/{code}"

    redirected = handle_http(svc, "GET", f"/{code}", None)
    assert redirected.status == 302
    assert redirected.header_map()["Location"] == "https://example.com/x"
    assert redirected.header_map()["Cache-Control"] == "no-store"


def test_health():
    svc = build_memory_service()
    resp = handle_http(svc, "GET", "/health", None)
    assert resp.status == 200
    assert json.loads(resp.body)["ok"] is True


def test_bad_json():
    svc = build_memory_service()
    resp = handle_http(svc, "POST", "/urls", "not-json")
    assert resp.status == 400


def test_lambda_write_event_shape():
    from url_shortener import handlers

    handlers._service = build_memory_service()
    event = {
        "rawPath": "/urls",
        "requestContext": {
            "domainName": "abc.execute-api.us-east-1.amazonaws.com",
            "http": {"method": "POST", "path": "/urls"},
        },
        "body": json.dumps({"long_url": "https://example.com/lambda"}),
        "isBase64Encoded": False,
    }
    resp = handlers.handle_write(event, None)
    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert body["short_url"].startswith("https://abc.execute-api.us-east-1.amazonaws.com/")


def test_lambda_read_event_shape():
    from url_shortener import handlers

    svc = build_memory_service()
    created = handle_http(
        svc, "POST", "/urls", json.dumps({"long_url": "https://example.com/r", "custom_alias": "abc123"})
    )
    assert created.status == 201
    handlers._service = svc
    event = {
        "rawPath": "/abc123",
        "pathParameters": {"short_code": "abc123"},
        "requestContext": {"http": {"method": "GET", "path": "/abc123"}},
    }
    resp = handlers.handle_read(event, None)
    assert resp["statusCode"] == 302
    assert resp["headers"]["Location"] == "https://example.com/r"
