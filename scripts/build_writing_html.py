"""Generate an HTML companion for every writing/*.md page.

Why: Markdown alone says nothing a machine can parse about WHO wrote it. These
HTML versions carry Article schema whose author points at the Person record on
the homepage, which is the link that ties your name to your subject matter.

Front matter is read from the top of each Markdown file:

    <!--
    title: The page title
    desc: One sentence for meta description and schema
    about: Topic one, Topic two, Topic three
    -->
"""
import io
import os
import re
import html
import json
from urllib.parse import quote, urlsplit
from build_sitemap import validate_last_updated


WRITING_INDEX_BEGIN = "<!-- BEGIN GENERATED WRITING INDEX -->"
WRITING_INDEX_END = "<!-- END GENERATED WRITING INDEX -->"


def script_json(value):
    """Serialize data without allowing HTML script termination."""
    return (json.dumps(value, ensure_ascii=True).replace("<", "\\u003c")
            .replace(">", "\\u003e").replace("&", "\\u0026"))


def parse_front_matter(md):
    m = re.match(r"\s*<!--(.*?)-->", md, re.S)
    meta = {}
    if m:
        for line in m.group(1).strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        md = md[m.end():].lstrip()
    return meta, md


def md_to_html(md):
    # Strip HTML comments (including multiline). A comment would otherwise
    # be collected as a paragraph and rendered as a visible escaped <p>
    # block, which leaks author guidance to the rendered page and to
    # agents that fetch the HTML companion.
    # Preserve literal comments inside fenced examples while removing guidance.
    segments = re.split(r"(^[ \t]*`{3,}[^\n]*\n.*?(?:^[ \t]*`{3,}[ \t]*$|\Z))", md, flags=re.M | re.S)
    md = "".join(part if i % 2 else re.sub(r"<!--.*?-->", "", part, flags=re.S)
                 for i, part in enumerate(segments))
    lines = md.split("\n")
    out, i = [], 0
    in_ul = in_ol = False

    def close():
        nonlocal in_ul, in_ol
        if in_ul: out.append("</ul>"); in_ul = False
        if in_ol: out.append("</ol>"); in_ol = False

    def inline(s):
        s = html.escape(s, quote=True)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        inert_links = []
        def link(match):
            label, escaped_target = match.groups()
            target = html.unescape(escaped_target).strip()
            try:
                scheme = urlsplit(target).scheme.lower()
            except ValueError:
                scheme = "unsafe"
            unsafe = (
                not target
                or target.startswith("//")
                or "\\" in target
                or any(ord(character) < 0x20 or ord(character) == 0x7f for character in target)
                or scheme not in {"", "http", "https", "mailto"}
            )
            if unsafe:
                placeholder = '<span data-inert-markdown-link="%d"></span>' % len(inert_links)
                inert_links.append((placeholder, "%s (%s)" % (label, escaped_target)))
                return placeholder
            return '<a href="%s">%s</a>' % (escaped_target, label)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)
        s = re.sub(r"(?<![\">=/\w])(https?://[^\s<),]+)", r'<a href="\1">\1</a>', s)
        for placeholder, inert_text in inert_links:
            s = s.replace(placeholder, inert_text)
        return s

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()

        if not s:
            close(); i += 1; continue

        fence = re.fullmatch(r"(`{3,})([^`]*)", s)
        if fence:
            close()
            marker, language = fence.groups()
            language = language.strip()
            i += 1
            code = []
            while i < len(lines) and not re.fullmatch(r"`{%d,}\s*" % len(marker), lines[i].strip()):
                code.append(lines[i]); i += 1
            if i < len(lines):
                i += 1
            css = ' class="language-%s"' % language if re.fullmatch(r"[A-Za-z0-9_-]{1,32}", language) else ""
            out.append("<pre><code%s>%s</code></pre>" % (css, html.escape("\n".join(code))))
            continue

        if s == "---":
            close(); out.append("<hr>"); i += 1; continue

        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            close()
            lvl = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2)), lvl))
            i += 1; continue

        if s.startswith("> "):
            close()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip()); i += 1
            out.append("<blockquote><p>%s</p></blockquote>" % inline(" ".join(buf)))
            continue

        # table
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i+1].strip()):
            close()
            hdr = [c.strip() for c in s.strip("|").split("|")]
            out.append("<table><thead><tr>" + "".join("<th>%s</th>" % inline(c) for c in hdr) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue

        m = re.match(r"^[-*]\s+(.*)$", s)
        if m:
            if in_ol: out.append("</ol>"); in_ol = False
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append("<li>%s</li>" % inline(m.group(1))); i += 1; continue

        m = re.match(r"^\d+\.\s+(.*)$", s)
        if m:
            if in_ul: out.append("</ul>"); in_ul = False
            if not in_ol: out.append("<ol>"); in_ol = True
            out.append("<li>%s</li>" % inline(m.group(1))); i += 1; continue

        close()
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|[-*]\s|\d+\.\s|\||>|`{3,}|---$)", lines[i].strip()):
            buf.append(lines[i].strip()); i += 1
        # A reserved block prefix is not necessarily a valid block. Consume it
        # as literal paragraph text when none of the block parsers matched so
        # malformed table or quote-like prose cannot stall the renderer.
        if not buf:
            buf.append(s); i += 1
        out.append("<p>%s</p>" % inline(" ".join(buf)))

    close()
    return "\n".join(out)



SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | {name}</title>
<meta name="description" content="{desc}">
<meta name="author" content="{name}">
<link rel="canonical" href="https://{domain}/writing/{slug}.html">
<link rel="alternate" type="text/markdown" href="/writing/{slug}.md" title="This page in Markdown">
<link rel="describedby" href="/llms.txt">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://{domain}/writing/{slug}.html">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "@id": "https://{domain}/writing/{slug}.html#article",
  "headline": {title_json},
  "description": {desc_json},
  "url": "https://{domain}/writing/{slug}.html",
  "mainEntityOfPage": "https://{domain}/writing/{slug}.html",
  "inLanguage": "en",
  {published_line}
  "dateModified": "{date}",
  "author": {{
    "@type": "Person",
    "@id": "https://{domain}/#person",
    "name": {name_json},
    "url": "https://{domain}/",
    "jobTitle": {title_role_json}
  }},
  "publisher": {{ "@type": "Person", "@id": "https://{domain}/#person", "name": {name_json} }},
  "about": [{about_json}]
}}
</script>
{style}
<style>
body {{ overflow-wrap: anywhere; }}
:focus-visible {{ outline: 3px solid currentColor; outline-offset: 4px; }}
.skip-link {{ position: absolute; left: 1rem; top: -5rem; background: white; color: black; padding: .5rem; }}
.skip-link:focus {{ top: 1rem; }}
pre, .table-scroll {{ overflow-x: auto; max-width: 100%; }}
pre {{ padding: 1rem; background: var(--code-bg, #f4f6f9); }}
h2, h3, h4 {{ scroll-margin-top: 1rem; }}
.outline {{ border-left: 3px solid var(--line, #ddd); padding-left: 1rem; margin: 2rem 0; }}
@media print {{ .skip-link, .outline {{ display: none; }} a {{ color: inherit; }} .wrap {{ max-width: none; padding: 0; }} }}
</style>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to content</a>
<div class="wrap">
<p><a href="/">{name}</a> / <a href="/writing/{slug}.md">this page in Markdown</a></p>
<main id="main-content">
{outline}
{content}
</main>
<footer><p>Contact: <a href="mailto:{email}">{email}</a></p></footer>
</div>
</body>
</html>
"""


def article_outline(content):
    """Add stable unique fragment IDs to rendered headings, excluding code."""
    used = {"main-content"}
    entries = []
    def heading(match):
        level, label = match.groups()
        plain = html.unescape(re.sub(r"<[^>]+>", "", label))
        base = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-") or "section"
        identifier, suffix = base, 2
        while identifier in used:
            identifier = "%s-%d" % (base, suffix); suffix += 1
        used.add(identifier)
        if level != "1":
            entries.append('<li><a href="#%s">%s</a></li>' % (identifier, html.escape(plain)))
        return '<h%s id="%s">%s</h%s>' % (level, identifier, label, level)
    content = re.sub(r"<h([1-4])>(.*?)</h\1>", heading, content)
    content = content.replace("<table>", '<div class="table-scroll" role="region" aria-label="Article table" tabindex="0"><table>')
    content = content.replace("</table>", "</table></div>")
    outline = '<nav class="outline" aria-label="On this page"><p>On this page</p><ul>%s</ul></nav>' % "".join(entries) if entries else ""
    return content, outline


def render_page(slug, source, cfg, style=""):
    """Render one writing page without requiring its slug to be a local filename."""
    import json as _json

    meta, md = parse_front_matter(source)
    title = meta.get("title") or slug.replace("-", " ").title()
    desc = meta.get("desc", "")
    about = [a.strip() for a in meta.get("about", "").split(",") if a.strip()]
    modified = validate_last_updated(meta.get("updated") or cfg.get("LAST_UPDATED"))
    published = validate_last_updated(meta["published"]) if meta.get("published") else None
    if published and published > modified:
        raise ValueError("article published date cannot follow updated date")
    content, outline = article_outline(md_to_html(md))
    return SHELL.format(
        title=html.escape(title, quote=True),
        desc=html.escape(desc, quote=True),
        slug=quote(slug, safe="-._~"),
        domain=html.escape(cfg.get("DOMAIN", ""), quote=True),
        name=html.escape(cfg.get("FULL_NAME", ""), quote=True),
        email=html.escape(cfg.get("EMAIL", ""), quote=True),
        date=modified,
        published_line='"datePublished": %s,' % script_json(published) if published else "",
        title_json=script_json(title),
        desc_json=script_json(desc),
        name_json=script_json(cfg.get("FULL_NAME", "")),
        title_role_json=script_json(cfg.get("JOB_TITLE", "")),
        about_json=", ".join(script_json(a) for a in about),
        style=style,
        content=content,
        outline=outline,
    )


def update_writing_index(site_dir, entries):
    """Replace the home-page writing list from canonical Markdown pages."""
    index_path = os.path.join(site_dir, "index.html")
    if not os.path.isfile(index_path):
        return
    with io.open(index_path, encoding="utf-8") as source:
        document = source.read()
    pattern = re.compile(
        re.escape(WRITING_INDEX_BEGIN)
        + r".*?"
        + re.escape(WRITING_INDEX_END),
        re.S,
    )
    if not pattern.search(document):
        return
    lines = [WRITING_INDEX_BEGIN, "<ul>"]
    for slug, title in entries:
        lines.append(
            '  <li><a href="/writing/%s.html">%s</a></li>'
            % (quote(slug, safe="-._~"), html.escape(title, quote=True))
        )
    lines.extend(("</ul>", WRITING_INDEX_END))
    document = pattern.sub("\n".join(lines), document, count=1)
    with io.open(index_path, "w", encoding="utf-8", newline="") as output:
        output.write(document)


def run(site_dir, cfg):
    wr = os.path.join(site_dir, "writing")
    idx = os.path.join(site_dir, "index.html")
    style = ""
    if os.path.exists(idx):
        with io.open(idx, encoding="utf-8") as index:
            m = re.search(r"<style>.*?</style>", index.read(), re.S)
        style = m.group(0) if m else ""

    entries = []
    if os.path.isdir(wr):
        for f in sorted(os.listdir(wr)):
            if not f.endswith(".md"):
                continue
            slug = f[:-3]
            with io.open(os.path.join(wr, f), encoding="utf-8") as source:
                markdown = source.read()
            meta, _ = parse_front_matter(markdown)
            title = meta.get("title") or slug.replace("-", " ").title()
            entries.append((slug, title))
            page = render_page(slug, markdown, cfg, style)
            with io.open(os.path.join(wr, slug + ".html"), "w", encoding="utf-8", newline="") as output:
                output.write(page)
            print("  wrote writing/%s.html" % slug)
    update_writing_index(site_dir, entries)
