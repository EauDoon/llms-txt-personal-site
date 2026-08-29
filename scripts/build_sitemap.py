"""Generate a sitemap from the public files that exist in a built site."""

import io
import os
import re
from datetime import date
from urllib.parse import quote
from xml.sax.saxutils import escape


PUBLIC_SUFFIXES = (".html", ".md", ".txt")
EXCLUDED_FILES = {"404.html", "robots.txt"}


def validate_last_updated(value):
    """Return an exact, calendar-valid YYYY-MM-DD date or raise ValueError."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("LAST_UPDATED must be a calendar-valid YYYY-MM-DD date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("LAST_UPDATED must be a calendar-valid YYYY-MM-DD date") from exc
    return value


def public_paths(site_dir):
    """Return deterministic, URL-encoded paths for indexable build artifacts."""
    paths = []
    for dirpath, dirnames, filenames in os.walk(site_dir):
        dirnames[:] = sorted(name for name in dirnames if not name.startswith("."))
        for filename in sorted(filenames):
            if filename.startswith(".") or filename in EXCLUDED_FILES:
                continue
            if not filename.lower().endswith(PUBLIC_SUFFIXES):
                continue
            relative = os.path.relpath(os.path.join(dirpath, filename), site_dir).replace(os.sep, "/")
            paths.append("/" if relative == "index.html" else "/" + quote(relative, safe="/-._~"))
    return sorted(set(paths), key=lambda path: (path != "/", path))


def public_urls(site_dir, domain):
    return ["https://%s%s" % (domain, path) for path in public_paths(site_dir)]


def run(site_dir, cfg):
    domain = cfg["DOMAIN"]
    last_updated = validate_last_updated(cfg.get("LAST_UPDATED"))
    urls = public_urls(site_dir, domain)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        lines.extend(["  <url>", "    <loc>%s</loc>" % escape(url)])
        if last_updated:
            lines.append("    <lastmod>%s</lastmod>" % escape(str(last_updated)))
        lines.append("  </url>")
    lines.append("</urlset>")
    output = "\n".join(lines) + "\n"
    with io.open(os.path.join(site_dir, "sitemap.xml"), "w", encoding="utf-8", newline="") as sitemap:
        sitemap.write(output)
    print("  wrote sitemap.xml from %d public files" % len(urls))
