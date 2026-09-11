"""URL shortener domain package. Transport (HTTP / Lambda) lives in handlers and http_app."""

from url_shortener.service import UrlShortener

__all__ = ["UrlShortener"]
