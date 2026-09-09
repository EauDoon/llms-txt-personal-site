"""Explicit editorial metadata and public-artifact selection."""
import re
from pathlib import PurePosixPath

from build_writing_html import parse_front_matter
from build_sitemap import validate_last_updated

FIELDS = {'title', 'desc', 'about', 'published', 'updated', 'status'}


def article_metadata(source):
    source = source.removeprefix('\ufeff')
    leading = re.match(r'\s*<!--(.*?)-->', source, re.DOTALL)
    if source.lstrip().startswith('<!--') and leading is None:
        raise ValueError('article metadata comment is not closed')
    seen = set()
    if leading:
        for line in leading[1].splitlines():
            line = line.strip()
            if not line:
                continue
            if ':' not in line:
                if re.search(r'\bstatus\b', line, re.IGNORECASE):
                    raise ValueError('article status must use status: draft or status: published')
                continue
            key = line.split(':', 1)[0].strip().lower()
            if key not in FIELDS or key in seen:
                raise ValueError('unknown or duplicate article metadata field: ' + key)
            seen.add(key)
    meta, body = parse_front_matter(source)
    status = meta.get('status', 'published')
    if status not in {'draft', 'published'}:
        raise ValueError('article status must be exactly draft or published')
    return dict(meta, status=status), body


def validate_article_dates(meta, fallback):
    updated = validate_last_updated(meta.get('updated') or fallback)
    published = meta.get('published')
    if published:
        validate_last_updated(published)
        if published > updated:
            raise ValueError('article published date cannot follow updated date')
    return updated


def publication_exclusions(sources, fill, cfg):
    """Select drafts before any source bytes are copied into the public stage.

    The caller has already checked source types, links, count and byte budgets.
    A draft also suppresses a same-stem hand-written HTML companion.
    """
    excluded = set()
    for source, _, relative in sources:
        path = PurePosixPath(relative.replace('\\', '/'))
        if not path.parts or path.parts[0].casefold() != 'writing' or path.suffix.casefold() != '.md':
            continue
        with open(source, encoding='utf-8') as stream:
            text = stream.read()
        raw, _ = article_metadata(text)
        if raw['status'] == 'draft':
            excluded.update((str(path).casefold(), str(path.with_suffix('.html')).casefold()))
        else:
            meta, _ = article_metadata(fill(text, cfg))
            validate_article_dates(meta, cfg['LAST_UPDATED'])
    return excluded
