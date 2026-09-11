"""Explicit editorial metadata and public-artifact selection."""
import re
import os
import unicodedata
from pathlib import Path, PurePosixPath

from build_writing_html import parse_front_matter
from build_sitemap import validate_last_updated

FIELDS = {'title', 'desc', 'about', 'published', 'updated', 'status'}


def article_topics(meta):
    topics = [' '.join(value.split()) for value in meta.get('about', '').split(',') if value.strip()]
    if len(topics) > 12 or any(len(topic) > 80 for topic in topics):
        raise ValueError('article about metadata allows at most 12 topics of 80 characters each')
    return list(dict.fromkeys(topics))


def article_metadata(source):
    source = re.sub(r'^[\s\ufeff]+', '', source)
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
    article_topics(meta)
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


def review_articles(template, cfg):
    """Read bounded article sources and report editorial work without mutation."""
    from build import fill, is_link_like
    from build_inventory import MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES
    from build_writing_html import markdown_display
    template = Path(template)
    writing = template / 'writing'
    if not template.is_dir():
        raise ValueError('template directory is missing')
    for path in (template, writing):
        if path.exists() and (is_link_like(path) or not path.is_dir()):
            raise ValueError('editorial review requires real directories')
    records, total = [], 0
    def title_key(value):
        return unicodedata.normalize('NFC', ' '.join(value.split())).casefold()
    for directory, dirs, files in os.walk(writing):
        for name in dirs + files:
            if is_link_like(Path(directory) / name):
                raise ValueError('editorial review refuses link-like sources')
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix.lower() != '.md':
                continue
            total += path.stat().st_size
            if len(records) >= MAX_FILES or path.stat().st_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                raise ValueError('editorial review exceeds the source budget')
            record = {'path': path.relative_to(template).as_posix(), 'status': 'invalid', 'title': path.stem,
                      'errors': [], 'warnings': []}
            try:
                source = path.read_text(encoding='utf-8')
                raw, _ = article_metadata(source)
                meta, body = article_metadata(fill(source, cfg))
                record.update(status=raw['status'], title=meta.get('title') or path.stem,
                              published=meta.get('published'), updated=meta.get('updated'))
                validate_article_dates(meta, cfg['LAST_UPDATED'])
                for key in ('title', 'desc', 'about'):
                    if not meta.get(key):
                        record['warnings'].append('add ' + key + ' metadata')
                if not meta.get('updated'):
                    record['warnings'].append('review date uses site LAST_UPDATED; add updated for an article-specific date')
                text, heading = markdown_display(body)
                if meta.get('title') and heading and title_key(meta['title']) != title_key(heading):
                    record['warnings'].append('article heading differs from title metadata; review reader-facing identity')
                if not text.strip() or text.strip() == (heading or '').strip():
                    record['warnings'].append('add article body before publication')
            except (OSError, UnicodeError, ValueError) as exc:
                record['errors'].append(str(exc))
            records.append(record)
    records.sort(key=lambda record: record['path'])
    titles = {}
    for record in records:
        if not record['errors']:
            titles.setdefault(title_key(record['title']), []).append(record)
    for duplicates in titles.values():
        if len(duplicates) > 1:
            for record in duplicates:
                others = ', '.join(other['path'] for other in duplicates[:6] if other is not record)
                if len(duplicates) > 6:
                    others += ' (and more; %d articles share this title)' % len(duplicates)
                record['warnings'].append('duplicate title also used by: ' + others)
    return {'version': 1, 'scope': 'Local editorial structure, not fact verification or publication approval.',
            'articles': records, 'drafts': sum(r['status'] == 'draft' for r in records),
            'published': sum(r['status'] == 'published' for r in records),
            'errors': sum(len(r['errors']) for r in records),
            'publication_warnings': sum(len(r['warnings']) for r in records if r['status'] == 'published')}
