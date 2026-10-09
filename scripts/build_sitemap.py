"""Generate a sitemap from the public files that exist in a built site."""

import os
import re
from datetime import date
from urllib.parse import quote
from xml.sax.saxutils import escape

PUBLIC_SUFFIXES = (".html", ".md", ".txt")
EXCLUDED_FILES = {"404.html", "robots.txt"}
# Accepted spellings of the optional search-engine ownership proofs.
VERIFICATION_TOKENS = {
    "bing_msvalidate": r"[A-Za-z0-9]{8,64}",
    "google_html_file": r"google[0-9a-f]{8,32}\.html",
    "indexnow_key": r"[A-Za-z0-9-]{8,128}",
}


def validate_last_updated(value):
    """Return an exact, calendar-valid YYYY-MM-DD date or raise ValueError."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("LAST_UPDATED must be a calendar-valid YYYY-MM-DD date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("LAST_UPDATED must be a calendar-valid YYYY-MM-DD date") from exc
    return value


def verification_files(cfg):
    """Return the root file names the configured search-engine proofs publish.

    Raises ValueError for a token that is not a plain proof value, because the
    names become files at the site root. Proofs are for search engines, not
    readers, so they stay out of the sitemap and the page checks.
    """
    verification = cfg.get("verification", {})
    if verification is None:
        verification = {}
    if not isinstance(verification, dict):
        raise ValueError("verification must be an object")
    for key, pattern in VERIFICATION_TOKENS.items():
        value = verification.get(key, "")
        if not isinstance(value, str) or (value and not re.fullmatch(pattern, value)):
            raise ValueError("verification.%s is not a valid token" % key)
    names = set()
    if verification.get("google_html_file"):
        names.add(verification["google_html_file"])
    if verification.get("indexnow_key"):
        names.add(verification["indexnow_key"] + ".txt")
    return names


def public_paths(site_dir, excluded=()):
    """Return deterministic, URL-encoded paths for indexable build artifacts."""
    paths = []
    for dirpath, dirnames, filenames in os.walk(site_dir):
        dirnames[:] = sorted(name for name in dirnames if not name.startswith("."))
        at_root = dirpath == os.fspath(site_dir)
        for filename in sorted(filenames):
            if filename.startswith(".") or filename in EXCLUDED_FILES:
                continue
            if at_root and filename in excluded:
                continue
            if not filename.lower().endswith(PUBLIC_SUFFIXES):
                continue
            relative = os.path.relpath(os.path.join(dirpath, filename), site_dir).replace(os.sep, "/")
            paths.append("/" if relative == "index.html" else "/" + quote(relative, safe="/-._~"))
    return sorted(set(paths), key=lambda path: (path != "/", path))


def public_urls(site_dir, domain, excluded=()):
    return ["https://%s%s" % (domain, path) for path in public_paths(site_dir, excluded)]


def run(site_dir, cfg):
    domain = cfg["DOMAIN"]
    last_updated = validate_last_updated(cfg.get("LAST_UPDATED"))
    urls = public_urls(site_dir, domain, verification_files(cfg))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        lines.extend(["  <url>", "    <loc>%s</loc>" % escape(url)])
        if last_updated:
            lines.append("    <lastmod>%s</lastmod>" % escape(str(last_updated)))
        lines.append("  </url>")
    lines.append("</urlset>")
    output = "\n".join(lines) + "\n"
    with open(os.path.join(site_dir, "sitemap.xml"), "w", encoding="utf-8", newline="") as sitemap:
        sitemap.write(output)
    print("  wrote sitemap.xml from %d public files" % len(urls))
