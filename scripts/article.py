"""Create and review local articles; never publish or deploy them."""
import argparse
import html
import json
import re
from pathlib import Path

from build import is_link_like, load_config
from build_llms_index import _safe_label
from publishing import review_articles
from build_sitemap import validate_last_updated

ROOT = Path(__file__).resolve().parents[1]


def one_line(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or len(value.splitlines()) != 1 or any(ord(c) < 32 for c in value):
        raise ValueError('%s must be a nonempty single line of at most %d characters' % (label, limit))
    return value.strip()


def create_article(repo, slug, title, description='', topics=(), body_path=None, published=None, updated=None):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or len(slug) > 80:
        raise ValueError('slug must contain at most 80 lowercase letters, digits and single hyphens')
    if re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])', slug):
        raise ValueError('slug is reserved by Windows')
    title = one_line(title, 'title', 200)
    if description:
        description = one_line(description, 'description', 500)
    if len(topics) > 12:
        raise ValueError('at most 12 topics are allowed')
    topics = [one_line(topic, 'topic', 80) for topic in topics]
    if any(',' in topic for topic in topics):
        raise ValueError('a topic cannot contain a comma')
    template = Path(repo) / 'template'
    writing = template / 'writing'
    for directory in (Path(repo), template, writing):
        if directory.exists() or directory.is_symlink():
            if is_link_like(directory) or not directory.is_dir():
                raise ValueError('article directory must be a real directory')
    if not template.is_dir():
        raise ValueError('template directory is missing')
    # Escape comment syntax and template delimiters before inserting metadata.
    def metadata(value):
        return html.escape(value, quote=False).replace('{', '&#123;').replace('}', '&#125;')
    lines = ['<!--', 'status: draft', 'title: ' + metadata(title)]
    for key, value in (('published', published), ('updated', updated)):
        if value is not None:
            lines.append(key + ': ' + validate_last_updated(value))
    if published and updated and published > updated:
        raise ValueError('article published date cannot follow updated date')
    if description:
        lines.append('desc: ' + metadata(description))
    if topics:
        lines.append('about: ' + metadata(', '.join(dict.fromkeys(topics))))
    heading = _safe_label(title).replace('{', '&#123;').replace('}', '&#125;')
    body = '# ' + heading + '\n\n'
    if body_path is not None:
        from build_inventory import MAX_FILE_BYTES
        source = Path(body_path)
        if is_link_like(source) or not source.is_file() or source.stat().st_size > MAX_FILE_BYTES:
            raise ValueError('body source must be a bounded real file')
        body = source.read_text(encoding='utf-8-sig')
        if not body.strip() or '\x00' in body:
            raise ValueError('body source must contain nonempty UTF-8 Markdown')
        if body.lstrip().startswith('<!--'):
            raise ValueError('body source must not start with metadata; supply metadata through options')
    lines += ['-->', body]
    writing.mkdir(exist_ok=True)
    reserved = {slug + '.md', slug + '.html'}
    if any(path.name.casefold() in reserved for path in writing.iterdir()):
        raise FileExistsError('article source or HTML companion already exists')
    target = writing / (slug + '.md')
    with target.open('x', encoding='utf-8', newline='') as stream:
        stream.write('\n'.join(lines))
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    new = commands.add_parser('new', help='create an unpublished article without overwriting')
    new.add_argument('slug')
    new.add_argument('--title', required=True)
    new.add_argument('--description', default='')
    new.add_argument('--topic', action='append', default=[])
    new.add_argument('--body-file', type=Path, help='import UTF-8 Markdown body into the new draft')
    new.add_argument('--published', help='declared publication date, YYYY-MM-DD; article remains a draft')
    new.add_argument('--updated', help='declared article review date, YYYY-MM-DD')
    review = commands.add_parser('review', help='report local editorial status without building')
    review.add_argument('--json', action='store_true', help='emit a machine-readable report')
    review.add_argument('--strict', action='store_true', help='also fail on published-article warnings')
    args = parser.parse_args(argv)
    try:
        if args.command == 'review':
            report = review_articles(ROOT / 'template', load_config())
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print('%d published articles, %d drafts' % (report['published'], report['drafts']))
                for row in report['articles']:
                    print('%s [%s]' % (row['path'], row['status']))
                    for issue in row['errors'] + row['warnings']:
                        print('  - ' + issue)
            return int(bool(report['errors'] or (args.strict and report['publication_warnings'])))
        path = create_article(ROOT, args.slug, args.title, args.description, args.topic, args.body_file,
                              args.published, args.updated)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, 'Article command failed: %s\n' % exc)
    print('Created draft: ' + str(path.relative_to(ROOT)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
