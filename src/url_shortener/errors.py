class UrlShortenerError(Exception):
    status_code = 400
    error_code = "bad_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(UrlShortenerError):
    status_code = 404
    error_code = "not_found"


class Gone(UrlShortenerError):
    status_code = 410
    error_code = "gone"


class Conflict(UrlShortenerError):
    status_code = 409
    error_code = "conflict"


class Unavailable(UrlShortenerError):
    status_code = 503
    error_code = "unavailable"
