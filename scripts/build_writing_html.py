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
import html
import json
import os
import re
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit
from build_sitemap import validate_last_updated

WRITING_INDEX_BEGIN = "<!-- BEGIN GENERATED WRITING INDEX -->"
WRITING_INDEX_END = "<!-- END GENERATED WRITING INDEX -->"
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")


def inline_parts(text):
    """Yield prose and literal code using matching backtick-run lengths."""
    position = 0
    for match in INLINE_CODE.finditer(text):
        yield False, text[position:match.start()]
        yield True, match[2]
        position = match.end()
    yield False, text[position:]


def script_json(value):
    """Serialize data without allowing HTML script termination."""
    return (json.dumps(value, ensure_ascii=True).replace("<", "\\u003c")
            .replace(">", "\\u003e").replace("&", "\\u0026"))


def parse_front_matter(md):
    m = re.match(r"\s*<!--(.*?)-->", md, re.DOTALL)
    meta = {}
    if m:
        for line in m.group(1).strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = html.unescape(v.strip())
        md = md[m.end():].lstrip()
    return meta, md


def opening_fence(line):
    return re.fullmatch(r"(`{3,})([^`]*)", line.strip())


def closes_fence(line, marker):
    candidate = line.strip()
    return len(candidate) >= len(marker) and candidate.strip("`") == ""


def strip_guidance_comments(md):
    """Keep fenced examples literal and omit only comments outside them."""
    output, marker, in_comment = [], None, False
    for line in md.split("\n"):
        if marker is not None:
            output.append(line)
            if closes_fence(line, marker):
                marker = None
            continue
        fence = opening_fence(line) if not in_comment else None
        if fence:
            marker = fence[1]
            output.append(line)
            continue
        visible, position = [], 0
        while position < len(line):
            token = "-->" if in_comment else "<!--"
            boundary = line.find(token, position)
            code = INLINE_CODE.search(line, position) if not in_comment else None
            if code and (boundary < 0 or code.start() < boundary):
                visible.append(line[position:code.end()])
                position = code.end()
                continue
            if boundary < 0:
                if not in_comment:
                    visible.append(line[position:])
                break
            if not in_comment:
                visible.append(line[position:boundary])
            in_comment = not in_comment
            position = boundary + len(token)
        clean = "".join(visible)
        # A comment can precede a fence on the same source line.
        fence = opening_fence(clean)
        if fence and not in_comment:
            marker = fence[1]
        output.append(clean)
    return "\n".join(output)


def md_to_html(md):
    md = strip_guidance_comments(md)
    lines = md.split("\n")
    out, i = [], 0
    in_ul = in_ol = False

    def close():
        nonlocal in_ul, in_ol
        if in_ul: out.append("</ul>"); in_ul = False
        if in_ol: out.append("</ol>"); in_ol = False

    def inline(s):
        literal_code, parts = [], []
        for code, value in inline_parts(s):
            if code:
                marker = '<span data-literal-code="%d"></span>' % len(literal_code)
                literal_code.append((marker, '<code>%s</code>' % html.escape(value, quote=True)))
                parts.append(marker)
            else:
                parts.append(html.escape(html.unescape(value), quote=True))
        s = "".join(parts)
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
        for marker, code in literal_code:
            s = s.replace(marker, code)
        return s

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()

        if not s:
            close(); i += 1; continue

        fence = opening_fence(s)
        if fence:
            close()
            marker, language = fence.groups()
            language = language.strip()
            i += 1
            code = []
            while i < len(lines) and not closes_fence(lines[i], marker):
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


def markdown_display(md):
    """Return rendered text and the first real H1's text from one HTML parse."""
    class Text(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self.heading, self.in_heading, self.heading_done = [], False, False

        def handle_starttag(self, tag, attrs):
            if tag == "h1" and not self.heading_done:
                self.in_heading = True

        def handle_data(self, value):
            self.parts.append(value)
            if self.in_heading:
                self.heading.append(value)

        def handle_endtag(self, tag):
            if tag == "h1" and self.in_heading:
                self.in_heading, self.heading_done = False, True
            if tag in {"h1", "h2", "h3", "h4", "p", "li", "pre", "tr"}:
                self.parts.append("\n")
            elif tag in {"td", "th"}:
                self.parts.append("\t")

    text = Text()
    text.feed(md_to_html(md))
    text.close()
    return "".join(text.parts).strip(), "".join(text.heading).strip()


def visible_markdown_text(md):
    return markdown_display(md)[0]



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
<footer><p>Contact: <a href="mailto:{email_uri}">{email}</a></p></footer>
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
        email_uri=quote(cfg.get("EMAIL", ""), safe="@"),
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
    with open(index_path, encoding="utf-8") as source:
        document = source.read()
    pattern = re.compile(
        re.escape(WRITING_INDEX_BEGIN)
        + r".*?"
        + re.escape(WRITING_INDEX_END),
        re.DOTALL,
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
    document = pattern.sub(lambda match: "\n".join(lines), document, count=1)
    with open(index_path, "w", encoding="utf-8", newline="") as output:
        output.write(document)


def run(site_dir, cfg):
    wr = os.path.join(site_dir, "writing")
    idx = os.path.join(site_dir, "index.html")
    style = ""
    if os.path.exists(idx):
        with open(idx, encoding="utf-8") as index:
            m = re.search(r"<style>.*?</style>", index.read(), re.DOTALL)
        style = m.group(0) if m else ""

    entries = []
    if os.path.isdir(wr):
        for f in sorted(os.listdir(wr)):
            if not f.endswith(".md"):
                continue
            slug = f[:-3]
            with open(os.path.join(wr, f), encoding="utf-8") as source:
                markdown = source.read()
            meta, _ = parse_front_matter(markdown)
            title = meta.get("title") or slug.replace("-", " ").title()
            entries.append((slug, title))
            page = render_page(slug, markdown, cfg, style)
            with open(os.path.join(wr, slug + ".html"), "w", encoding="utf-8", newline="") as output:
                output.write(page)
            print("  wrote writing/%s.html" % slug)
    update_writing_index(site_dir, entries)
