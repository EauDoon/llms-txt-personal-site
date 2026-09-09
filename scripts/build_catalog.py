"""Build reader discovery outputs from published Markdown, without dependencies."""
import html
import json
import re
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET
from build_sitemap import validate_last_updated

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
    build_search(site_dir, cfg, entries)
    build_feed(site_dir, cfg, entries)


def build_feed(site_dir, cfg, entries):
    """Atom uses declared article dates, falling back to the site's review date."""
    namespace = "http://www.w3.org/2005/Atom"
    ET.register_namespace("", namespace)
    def node(parent, tag, value=None, **attributes):
        element = ET.SubElement(parent, "{%s}%s" % (namespace, tag), attributes)
        element.text = value
        return element
    base = "https://" + cfg["DOMAIN"]
    feed = ET.Element("{%s}feed" % namespace)
    node(feed, "id", base + "/feed.xml")
    node(feed, "title", cfg["FULL_NAME"] + " writing")
    node(feed, "link", href=base + "/feed.xml", rel="self")
    node(feed, "link", href=base + "/writing.html")
    author = node(feed, "author")
    node(author, "name", cfg["FULL_NAME"])
    dates = [validate_last_updated(cfg["LAST_UPDATED"])]
    for entry in entries:
        updated = validate_last_updated(entry["meta"].get("updated") or cfg["LAST_UPDATED"])
        dates.append(updated)
        item = node(feed, "entry")
        node(item, "id", base + entry["url"])
        node(item, "title", entry["title"])
        node(item, "link", href=base + entry["url"])
        node(item, "summary", entry["description"])
        node(item, "updated", updated + "T00:00:00Z")
        if entry["meta"].get("published"):
            published = validate_last_updated(entry["meta"]["published"])
            if published > updated:
                raise ValueError("article published date cannot follow updated date")
            node(item, "published", published + "T00:00:00Z")
    node(feed, "updated", max(dates) + "T00:00:00Z")
    (Path(site_dir) / "feed.xml").write_bytes(ET.tostring(feed, encoding="utf-8", xml_declaration=True) + b"\n")


def build_search(site_dir, cfg, entries):
    records = []
    writing = {entry["source"]: entry for entry in entries}
    paths = sorted(Path(site_dir).glob("*.md")) + sorted((Path(site_dir) / "writing").glob("*.md"))
    for path in paths:
        source = "/" + quote(path.relative_to(site_dir).as_posix(), safe="/-._~")
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
        heading = re.search(r"^#\s+(.+)$", body, re.M)
        article = writing.get(source, {})
        records.append({"title": article.get("title") or (heading[1] if heading else path.stem.title()),
                        "url": article.get("url", source), "text": body[:100000]})
    (Path(site_dir) / "search-index.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
    links = ''.join('<li><a href="%s">%s</a></li>' % (r["url"], html.escape(r["title"])) for r in records)
    body = '''<form role="search"><label for="query">Search published pages</label>
<input id="query" type="search" maxlength="200" autocomplete="off" placeholder="Title, topic, or phrase">
<button type="reset">Clear search</button></form><p id="search-status" role="status" aria-live="polite">All published pages. Search requires JavaScript.</p>
<ul id="search-results">%s</ul><script src="/search.js" defer></script>''' % links
    (Path(site_dir) / "search.html").write_text(page("Search", body, cfg), encoding="utf-8", newline="")
