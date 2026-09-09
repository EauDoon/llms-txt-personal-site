"""Build reader discovery outputs from published Markdown, without dependencies."""
import html
import json
import re
from pathlib import Path
from urllib.parse import quote

from build_writing_html import parse_front_matter


def articles(site_dir):
    entries = []
    for path in sorted((Path(site_dir) / "writing").glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        entries.append({"title": meta.get("title") or path.stem.replace("-", " ").title(),
                        "description": meta.get("desc", ""),
                        "topics": [s.strip() for s in meta.get("about", "").split(",") if s.strip()],
                        "url": "/writing/" + quote(path.stem, safe="-._~") + ".html",
                        "source": "/writing/" + quote(path.name, safe="-._~"),
                        "body": body, "meta": meta})
    return entries


def page(title, body, cfg):
    esc = html.escape
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s | %s</title><link rel="describedby" href="/llms.txt">
<style>
:root { color-scheme: light dark; font: 17px/1.65 system-ui,sans-serif; }
body { max-width: 48rem; padding: 2rem 1.25rem; margin: auto; overflow-wrap: anywhere; }
a { color: light-dark(#1646ad,#94bbff); } :focus-visible { outline: 3px solid currentColor; outline-offset: 4px; }
li { margin-block: 1.25rem; } p { margin-block: .5rem; }
input,button { font: inherit; padding: .6rem; max-width: 100%%; box-sizing: border-box; }
input { width: 100%%; } .skip { position: absolute; top: -5rem; } .skip:focus { top: .5rem; }
</style></head><body><a class="skip" href="#main-content">Skip to content</a>
<nav aria-label="Site"><a href="/">%s</a> · <a href="/writing.html">Writing</a> · <a href="/llms.txt">Machine-readable index</a></nav>
<main id="main-content"><h1>%s</h1>%s</main></body></html>
''' % (esc(title), esc(cfg["FULL_NAME"]), esc(cfg["FULL_NAME"]), esc(title), body)


def run(site_dir, cfg):
    entries = articles(site_dir)
    rows = []
    for entry in entries:
        rows.append('<li><h2><a href="%s">%s</a></h2><p>%s</p><p>%s</p><a href="%s">Markdown source</a></li>' % (
            entry["url"], html.escape(entry["title"]), html.escape(entry["description"]),
            html.escape(" · ".join(entry["topics"])), entry["source"]))
    body = '<p>Browse %d writing page%s, with original Markdown sources.</p>' % (len(rows), "" if len(rows) == 1 else "s")
    body += '<ul>%s</ul>' % "".join(rows) if rows else '<p>No writing pages have been published.</p>'
    (Path(site_dir) / "writing.html").write_text(page("Writing", body, cfg), encoding="utf-8", newline="")
