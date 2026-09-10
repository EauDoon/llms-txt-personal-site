"""Readable companions for core pages, preserving canonical Markdown bytes."""
import html
from pathlib import Path
from urllib.parse import quote

from build_catalog import page
from build_writing_html import article_outline, markdown_display, md_to_html, parse_front_matter

RESERVED = {'index', 'writing', 'search', 'topics'}


def run(site_dir, cfg):
    for source in sorted(Path(site_dir).glob('*.md')):
        target = source.with_suffix('.html')
        if source.stem in RESERVED or target.exists():
            continue
        _, body = parse_front_matter(source.read_text(encoding='utf-8'))
        _, heading = markdown_display(body)
        title = heading or source.stem.replace('-', ' ').title()
        content, outline = article_outline(md_to_html(body))
        if not heading:
            content = '<h1>%s</h1>' % html.escape(title) + content
        route = '/' + quote(source.name, safe='-._~')
        content = outline + content + '<p><a href="%s">Read the original Markdown source</a></p>' % route
        target.write_text(page(title, content, cfg, source=route, heading=False), encoding='utf-8', newline='')
