"""Build reader discovery outputs from published Markdown, without dependencies."""
import html
import json
import hashlib
import unicodedata
from pathlib import Path
from urllib.parse import quote, unquote
from xml.etree import ElementTree as ET
from build_sitemap import validate_last_updated

from build_writing_html import parse_front_matter, markdown_display, reading_estimate
from build_llms_index import _safe_label
from publishing import article_topics


def markdown_label(value):
    """Keep discovery labels inert when a consumer renders the Markdown index."""
    return _safe_label(value)


def articles(site_dir):
    entries = []
    for path in sorted((Path(site_dir) / "writing").glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        entries.append({"title": meta.get("title") or path.stem.replace("-", " ").title(),
                        "description": meta.get("desc", ""),
                        "topics": article_topics(meta),
                        "url": "/writing/" + quote(path.stem, safe="-._~") + ".html",
                        "source": "/writing/" + quote(path.name, safe="-._~"),
                        "body": body, "meta": meta})
    entries.sort(key=lambda entry: (entry['title'].casefold(), entry['url']))
    entries.sort(key=lambda entry: entry['meta'].get('updated') or entry['meta'].get('published') or '', reverse=True)
    return entries


def date_labels(entry, cfg):
    meta = entry['meta']
    labels = []
    if meta.get('published'):
        labels.append(('Published', validate_last_updated(meta['published'])))
    if meta.get('updated'):
        labels.append(('Article updated', validate_last_updated(meta['updated'])))
    else:
        labels.append(('Site date (fallback)', validate_last_updated(cfg['LAST_UPDATED'])))
    return labels


def topic_key(topic):
    return unicodedata.normalize('NFC', ' '.join(topic.split())).casefold()


def topic_id(topic):
    return 'topic-' + hashlib.sha256(topic_key(topic).encode('utf-8')).hexdigest()[:20]


def topic_links(entry):
    return ' · '.join('<a href="/topics.html#%s">%s</a>' % (topic_id(topic), html.escape(topic))
                      for topic in entry['topics'])


def topic_groups(entries):
    groups = {}
    for entry in entries:
        for topic in entry['topics']:
            key = topic_key(topic)
            group = groups.setdefault(key, {'label': topic, 'id': topic_id(topic), 'entries': []})
            group['label'] = min(group['label'], topic)
            if entry not in group['entries']:
                group['entries'].append(entry)
    return [groups[key] for key in sorted(groups)]


def build_related(site_dir, entries):
    topic_sets = {entry['url']: {topic_key(topic) for topic in entry['topics']} for entry in entries}
    for entry in entries:
        topics = topic_sets[entry['url']]
        candidates = [(len(topics & topic_sets[candidate['url']]), candidate)
                      for candidate in entries if topics and candidate['url'] != entry['url']]
        candidates = sorted((pair for pair in candidates if pair[0]), key=lambda pair: -pair[0])[:3]
        body = '<nav aria-label="Related writing">'
        if candidates:
            body += '<p>More writing with shared authored topics:</p><ul>'
            body += ''.join('<li><a href="%s">%s</a></li>' % (candidate['url'], html.escape(candidate['title']))
                            for _, candidate in candidates)
            body += '</ul>'
        body += '<p><a href="/writing.html">Browse all writing</a></p></nav>'
        # Decode once to recover the local filename used to create this URL.
        path = Path(site_dir) / unquote(entry['url']).lstrip('/')
        if path.is_file():
            source = path.read_text(encoding='utf-8')
            path.write_text(source.replace('<!-- GENERATED RELATED WRITING -->', body), encoding='utf-8', newline='')


def build_topics(site_dir, cfg, entries):
    groups = topic_groups(entries)
    body = '<p>Browse writing by topics supplied by the author.</p>'
    markdown = '# Writing topics\n\nLast updated: %s\n\n' % cfg['LAST_UPDATED']
    if groups:
        body += '<nav aria-label="Topics on this page"><ul>' + ''.join(
            '<li><a href="#%s">%s</a></li>' % (group['id'], html.escape(group['label'])) for group in groups) + '</ul></nav>'
    else:
        body += '<p>No topics are published yet. <a href="/writing.html">Browse all writing</a>.</p>'
        markdown += 'No topics are published yet.\n'
    for group in groups:
        body += '<section aria-labelledby="%s"><h2 id="%s">%s</h2><ul>' % (group['id'], group['id'], html.escape(group['label']))
        markdown += '## %s\n\n' % markdown_label(group['label'])
        for entry in group['entries']:
            body += '<li><a href="%s">%s</a></li>' % (entry['url'], html.escape(entry['title']))
            markdown += '- [%s](%s)\n' % (markdown_label(entry['title']), entry['source'])
        body += '</ul></section>'
        markdown += '\n'
    (Path(site_dir) / 'topics.html').write_text(page('Topics', body, cfg), encoding='utf-8', newline='')
    (Path(site_dir) / 'topics.md').write_text(markdown, encoding='utf-8', newline='')


def page(title, body, cfg, source=None, heading=True):
    esc = html.escape
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s | %s</title><link rel="describedby" href="/llms.txt">
<link rel="alternate" type="text/markdown" href="%s" title="Source in Markdown">
<style>
:root { color-scheme: light dark; font: 17px/1.65 system-ui,sans-serif; }
body { max-width: 48rem; padding: 2rem 1.25rem; margin: auto; overflow-wrap: anywhere; }
a { color: light-dark(#1646ad,#94bbff); } :focus-visible { outline: 3px solid currentColor; outline-offset: 4px; }
li { margin-block: 1.25rem; } p { margin-block: .5rem; }
input,button,select { font: inherit; padding: .6rem; max-width: 100%%; min-height: 44px; box-sizing: border-box; }
input { width: 100%%; } .skip { position: absolute; top: -5rem; } .skip:focus { top: .5rem; }
form { display: grid; gap: .75rem; } label { display: block; } select { width: 100%%; }
.search-filters { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }
.search-actions { display: flex; flex-wrap: wrap; gap: .75rem; }
@media (max-width: 480px) { .search-filters { grid-template-columns: 1fr; } }
pre,.table-scroll { overflow-x: auto; max-width: 100%%; } pre { padding: 1rem; border: 1px solid currentColor; }
.outline { border-left: 2px solid currentColor; padding-left: 1rem; margin-block: 2rem; }
@media print { nav,.skip { display: none; } body { max-width: none; padding: 0; } }
</style></head><body><a class="skip" href="#main-content">Skip to content</a>
<nav aria-label="Site"><a href="/">%s</a> · <a href="/writing.html">Writing</a> · <a href="/topics.html">Topics</a> · <a href="/search.html">Search</a> · <a href="/llms.txt">Machine-readable index</a></nav>
<main id="main-content">%s%s</main></body></html>
''' % (esc(title), esc(cfg["FULL_NAME"]), esc(source or '/' + title.lower() + '.md', quote=True),
       esc(cfg["FULL_NAME"]), '<h1>%s</h1>' % esc(title) if heading else '', body)


def run(site_dir, cfg):
    entries = articles(site_dir)
    build_related(site_dir, entries)
    rows = []
    for entry in entries:
        dates = ' · '.join('%s: <time datetime="%s">%s</time>' % (label, date, date) for label, date in date_labels(entry, cfg))
        rows.append('<li><h2><a href="%s">%s</a></h2><p>%s</p><p>%s</p><p>%s</p><a href="%s">Markdown source</a></li>' % (
            entry["url"], html.escape(entry["title"]), html.escape(entry["description"]),
            dates + ' · ' + reading_estimate(entry['body']), topic_links(entry), entry["source"]))
    body = '<p>Browse %d writing page%s, with original Markdown sources.</p>' % (len(rows), "" if len(rows) == 1 else "s")
    body += '<p>Latest declared article dates first. Articles without dates follow in title order.</p>'
    body += '<ul>%s</ul>' % "".join(rows) if rows else '<p>No writing pages have been published.</p>'
    (Path(site_dir) / "writing.html").write_text(page("Writing", body, cfg), encoding="utf-8", newline="")
    markdown = "# Writing\n\nLast updated: %s\n\n" % cfg["LAST_UPDATED"]
    markdown += "\n".join(("- [%s](%s)" % (markdown_label(entry["title"]), entry["source"])) + (": " + html.escape(entry["description"], quote=False) if entry["description"] else "")
                          + ' (' + '; '.join(label + ': ' + date for label, date in date_labels(entry, cfg)) + ')' for entry in entries)
    (Path(site_dir) / "writing.md").write_text(markdown + "\n", encoding="utf-8", newline="")
    build_search(site_dir, cfg, entries)
    build_feed(site_dir, cfg, entries)
    build_topics(site_dir, cfg, entries)


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
        for topic in entry['topics']:
            node(item, 'category', term=topic)
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
    paths = [path for path in sorted(Path(site_dir).glob("*.md")) if path.name not in {"search.md", "writing.md", "topics.md"}] + sorted((Path(site_dir) / "writing").glob("*.md"))
    for path in paths:
        source = "/" + quote(path.relative_to(site_dir).as_posix(), safe="/-._~")
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        body, heading = markdown_display(body)
        article = writing.get(source, {})
        companion = path.with_suffix('.html')
        from llms_txt import has_link_relation
        readable = '/' + quote(companion.name, safe='-._~') if (path.parent == Path(site_dir) and companion.is_file()
                    and has_link_relation(companion.read_text(encoding='utf-8'), 'alternate', source, 'text/markdown')) else source
        records.append({"title": article.get("title") or heading or path.stem.title(),
                        "url": article.get("url", readable), "text": body[:100000],
                        "type": "article" if article else "page",
                        "topic_keys": sorted({topic_key(topic) for topic in article.get('topics', [])})})
    (Path(site_dir) / "search-index.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
    links = ''.join('<li><a href="%s">%s</a></li>' % (r["url"], html.escape(r["title"])) for r in records)
    options = ''.join('<option value="%s">%s</option>' % (html.escape(topic_key(group['label']), quote=True), html.escape(group['label']))
                      for group in topic_groups(entries))
    body = '''<p>Search runs in this browser. The page URL stores your query and filters for sharing or reloading.</p>
<form role="search"><div><label for="query">Search published pages</label>
<input id="query" name="q" type="search" maxlength="200" autocomplete="off" placeholder="Title, topic, or phrase"></div>
<div class="search-filters"><div><label for="page-type">Page type</label><select id="page-type" name="type"><option value="">All pages</option><option value="article">Writing</option><option value="page">Core pages</option></select></div>
<div><label for="topic">Topic</label><select id="topic" name="topic"><option value="">All topics</option>%s</select></div></div>
<div class="search-actions"><button type="submit">Search pages</button><button type="reset">Clear search</button></div></form>
<p id="search-status" role="status" aria-live="polite">All published pages. Search requires JavaScript.</p>
<button id="search-retry" type="button" hidden>Retry search</button>
<ul id="search-results">%s</ul><script src="/search.js" defer></script>''' % (options, links)
    (Path(site_dir) / "search.html").write_text(page("Search", body, cfg), encoding="utf-8", newline="")
    markdown = "# Search and page directory\n\nLast updated: %s\n\nSearch runs locally in the browser at /search.html. Published pages:\n\n" % cfg["LAST_UPDATED"]
    markdown += "\n".join("- [%s](%s)" % (markdown_label(record["title"]), record["url"]) for record in records)
    (Path(site_dir) / "search.md").write_text(markdown + "\n", encoding="utf-8", newline="")
