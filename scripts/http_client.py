"""Small standard-library HTTP client for live publication checks."""

from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirectHandler(HTTPRedirectHandler):
    """Expose redirect responses so the quality gate can fail closed on them."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


OPENER = build_opener(NoRedirectHandler())


def fetch_url(url, timeout=20):
    """Return status, headers, body, and any transport error without redirects."""
    try:
        request = Request(
            url,
            headers={"User-Agent": "llms-txt-personal-site-quality-check/1"},
        )
        with OPENER.open(request, timeout=timeout) as response:
            return response.status, response.headers, response.read(), ""
    except HTTPError as exc:
        try:
            body = exc.read()
        except OSError:
            body = b""
        return exc.code, exc.headers, body, ""
    except (HTTPException, OSError, ValueError) as exc:
        return 0, {}, b"", str(exc)
