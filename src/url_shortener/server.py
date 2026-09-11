"""Local HTTP server — same routes as API Gateway, in-memory stores."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from url_shortener.factory import build_memory_service
from url_shortener.http_app import handle_http
from url_shortener.service import UrlShortener


def make_handler(service: UrlShortener, public_base: str | Callable[[], str], quiet: bool = False):
    class Handler(BaseHTTPRequestHandler):
        def _handle(self, method: str, body: str | None) -> None:
            base = public_base() if callable(public_base) else public_base
            response = handle_http(service, method, self.path, body, public_base=base)
            self.send_response(response.status)
            for key, value in response.header_map().items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(response.body.encode("utf-8"))))
            self.end_headers()
            if response.body:
                self.wfile.write(response.body.encode("utf-8"))

        def do_GET(self) -> None:  # noqa: N802
            self._handle("GET", None)

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b""
            self._handle("POST", raw.decode("utf-8"))

        def log_message(self, fmt: str, *args) -> None:
            if quiet:
                return
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    public_base = f"http://{host}:{port}"
    service = build_memory_service(public_base=public_base)
    httpd = ThreadingHTTPServer((host, port), make_handler(service, public_base))
    print(f"URL shortener listening on {public_base}", flush=True)
    print("POST /urls   GET /{code}   GET /health", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down", flush=True)
        httpd.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Local URL shortener (in-memory)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
