"""Small standard-library HTTP client for live publication checks."""

from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirectHandler(HTTPRedirectHandler):
    """Expose redirect responses so the quality gate can fail closed on them."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


OPENER = build_opener(NoRedirectHandler())
MAX_RESPONSE_BYTES = 20 * 1024 * 1024


def read_body(response):
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Response exceeds the 20 MiB limit")
    return body


def fetch_url(url, timeout=20, user_agent="llms-txt-personal-site-quality-check"):
    """Return status, headers, body, and any transport error without redirects.

    The caller supplies the versioned User-Agent, so this module keeps no
    imports of its own and loads standalone.
    """
    try:
        request = Request(
            url,
            headers={"User-Agent": user_agent},
        )
        with OPENER.open(request, timeout=timeout) as response:
            return response.status, response.headers, read_body(response), ""
    except HTTPError as exc:
        try:
            with exc:
                return exc.code, exc.headers, read_body(exc), ""
        except (HTTPException, OSError, ValueError) as error:
            return 0, {}, b"", str(error)
    except (HTTPException, OSError, ValueError) as exc:
        return 0, {}, b"", str(exc)
