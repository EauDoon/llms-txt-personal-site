"""The response headers the shipped host configs promise, for the live checks.

template/_headers, template/.htaccess and template/vercel.json all send these.
tests/test_hosting.py keeps the table below in step with template/_headers,
so a change to the configs that the checks do not follow fails a test.
"""

import posixpath
import re
from urllib.parse import urlsplit

# File suffix -> (media type, Content-Disposition). A Markdown or text file
# served with another type, or as an attachment, downloads in a browser and
# is skipped by crawlers that trust the type.
FILE_TYPES = {
    ".md": ("text/markdown", "inline"),
    ".txt": ("text/plain", "inline"),
}
SITEMAP_TYPES = ("application/xml", "text/xml")
# Every response advertises the index, so an agent that fetches any URL can
# find it without parsing HTML.
DISCOVERY_LINK = ("/llms.txt", "describedby")
# Sent on the homepage beside nosniff and the Content-Security-Policy. None
# means any nonempty value.
HOMEPAGE_HEADERS = {"X-Frame-Options": "DENY", "Permissions-Policy": None}


def header_values(headers, name):
    """Return every value sent for one header, however the client stored them."""
    if hasattr(headers, "get_all"):
        return list(headers.get_all(name) or [])
    value = headers.get(name)
    return [] if value is None else [value]


def media_type(headers):
    """Return the lowercase media type of Content-Type, without parameters."""
    values = header_values(headers, "Content-Type")
    return values[0].split(";", 1)[0].strip().lower() if values else ""


def promised_file_type(path):
    """Return the (media type, disposition) promised for a URL path, or None."""
    return FILE_TYPES.get(posixpath.splitext(urlsplit(path).path)[1].lower())


def file_type_ok(path, headers):
    """Return whether a .md or .txt response has its promised type and disposition."""
    expected = promised_file_type(path)
    if expected is None:
        return True
    media, disposition = expected
    dispositions = [value.split(";", 1)[0].strip().lower() for value in header_values(headers, "Content-Disposition")]
    return media_type(headers) == media and dispositions == [disposition]


def has_discovery_link(headers, domain):
    """Return whether a Link header points at /llms.txt with rel=describedby.

    Hosts may send one Link header per value or join values with commas, and
    the target may be absolute.
    """
    target, relation = DISCOVERY_LINK
    allowed = {"<%s>" % target, "<https://%s%s>" % (domain.lower(), target)}
    for value in header_values(headers, "Link"):
        for link in re.findall(r"<[^>]*>[^,<]*", value):
            url, _, parameters = link.partition(">")
            if url.lower() + ">" not in allowed:
                continue
            for parameter in parameters.split(";"):
                name, _, rel = parameter.partition("=")
                if name.strip().lower() == "rel" and relation in rel.strip().strip('"').lower().split():
                    return True
    return False
