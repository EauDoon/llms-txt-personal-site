"""Integrated editorial and reader contracts for the static publisher."""
import sys
import json
import shutil
import tempfile
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build import build_site_staged, json_block
from build_writing_html import md_to_html
from email_addresses import contact_values
from publishing import article_metadata, review_articles
from article import create_article
from check_artifacts import audit
from xml.etree import ElementTree as ET
from build_catalog import topic_id
from review_build import review_candidate


class PublishingTests(unittest.TestCase):
    def test_plain_email_substitution_preserves_authored_entities_and_generated_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            cfg['EMAIL'] = 'a**tag@example.test'
            literal = 'Authored a&#42;&#42;tag@example.test and &lt;script&gt;.'
            (template / 'literal.md').write_text('# Literal\n\nContact: {{EMAIL}}\n\n' + literal, encoding='utf-8')
            (template / 'writing.md').write_text('# REPLACED_INDEX\n\n{{EMAIL}}', encoding='utf-8')
            (template / 'writing' / 'draft.md').write_text(
                '<!--\nstatus: draft\n-->\n# DRAFT_CONTACT\n{{EMAIL}}', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            output = (site / 'llms-full.txt').read_text(encoding='utf-8')
            self.assertIn('Contact: a**tag@example.test', output)
            self.assertIn(literal, output)
            self.assertNotIn('REPLACED_INDEX', output)
            self.assertNotIn('DRAFT_CONTACT', output)
            self.assertIn((site / 'writing.md').read_text(encoding='utf-8'), output)
            from build_llms_full import run
            run(str(site), cfg)
            output = (site / 'llms-full.txt').read_text(encoding='utf-8')
            self.assertIn((site / 'literal.md').read_text(encoding='utf-8'), output)

    def test_generated_catalog_pages_never_reuse_equal_source_snapshots(self):
        import build_catalog
        from build import fill
        generate = build_catalog.run
        for names in (('writing.md', 'topics.md', 'search.md'), ('Writing.md', 'TOPICS.md', 'Search.md')):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as directory:
                template, site, cfg = self.fixture(directory)
                cfg['EMAIL'] = 'a**tag@example.test'
                source = '# Generated\n\n{{EMAIL}}'
                for name in names:
                    original = template / name.lower()
                    if name != name.lower() and original.exists():
                        original.rename(template / name)
                    (template / name).write_text(source, encoding='utf-8')
                def same_bytes(directory, config):
                    generate(directory, config)
                    for name in ('writing.md', 'topics.md', 'search.md'):
                        (Path(directory) / name).write_text(fill(source, config), encoding='utf-8')
                with patch('build_catalog.run', side_effect=same_bytes):
                    build_site_staged(str(template), str(site), cfg)
                count = sum(path.read_text(encoding='utf-8').startswith('# Generated')
                            for path in site.glob('*.md'))
                self.assertEqual((site / 'llms-full.txt').read_text(encoding='utf-8').count(
                    '# Generated\n\na&#42;&#42;tag@example.test'), count)

    def test_plain_machine_records_preserve_configured_email_without_decoding_other_text(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            cfg['EMAIL'] = "a**tag|notes&x'@example.test"
            (template / 'literal.md').write_text('# Literal\n\nKeep &lt;script&gt; inert.\n', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            for name in ('llms.txt', 'llms-full.txt'):
                output = (site / name).read_text(encoding='utf-8')
                self.assertIn(cfg['EMAIL'], output)
                self.assertNotIn('a&#42;&#42;tag', output)
            self.assertIn('Keep &lt;script&gt; inert.', (site / 'llms-full.txt').read_text(encoding='utf-8'))
            self.assertIn('a&#42;&#42;tag', (site / 'contact.md').read_text(encoding='utf-8'))
            self.assertFalse(audit(site))

    def test_normalized_unicode_topics_preserve_the_metadata_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            for slug, topic in (('ligatures', '\ufb03' * 80), ('astral', '\U0001f600' * 80)):
                (template / 'writing' / (slug + '.md')).write_text(
                    '<!--\ntitle: ' + slug + '\nabout: ' + topic + '\n-->\n# Unicode topics\n', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            rows = {row['url']: row for row in json.loads((site / 'search-index.json').read_text(encoding='utf-8'))}
            self.assertEqual(rows['/writing/ligatures.html']['topic_keys'], ['ffi' * 80])
            self.assertEqual(rows['/writing/astral.html']['topic_keys'], ['\U0001f600' * 80])
            self.assertIn('value="' + 'ffi' * 80 + '"', (site / 'search.html').read_text(encoding='utf-8'))
            with self.assertRaisesRegex(ValueError, '80 characters'):
                article_metadata('<!--\nabout: ' + '\ufb03' * 81 + '\n-->\n# Too long')

    def test_core_companions_keep_wrapped_lists_and_following_blocks(self):
        source = ('# Wrapped lists\n\n1. First **ordered**\n   continued & safe.\n'
                  '2. Second ordered\n   more text.\n\n- First unordered\n'
                  '  continued `code`.\n* Second unordered\n\n'
                  '- Before fence\n  ```text\n<!-- literal -->\n  ```\n'
                  '- Before heading\n  ## Heading\n- Before quote\n  > Quote\n'
                  '- Before table\n  | A |\n  |---|\n  | B |\n'
                  '- Before rule\n  ---\n<!-- hidden guidance -->\nPlain paragraph.')
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            (template / 'wrapped.md').write_text(source, encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            output = (site / 'wrapped.html').read_text(encoding='utf-8')
            self.assertIn('<ol>\n<li>First <strong>ordered</strong> continued &amp; safe.</li>\n'
                          '<li>Second ordered more text.</li>\n</ol>', output)
            self.assertIn('<ul>\n<li>First unordered continued <code>code</code>.</li>\n'
                          '<li>Second unordered</li>\n</ul>', output)
            for block in ('<pre><code class="language-text">&lt;!-- literal --&gt;</code></pre>',
                          '<h2 id="heading">Heading</h2>', '<blockquote><p>Quote</p></blockquote>',
                          '<table>', '<hr>', '<p>Plain paragraph.</p>'):
                self.assertIn(block, output)
            self.assertNotIn('hidden guidance', output)

    def test_candidate_review_runs_real_gates_without_replacing_current_output(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            retired = template / 'retired.md'
            with self.assertRaisesRegex(ValueError, 'must not overlap'):
                review_candidate(template, template, cfg)
            retired.write_text('# Retired\n\nA synthetic page.\n', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            original = {str(p): p.read_bytes() for p in site.rglob('*') if p.is_file()}
            retired.unlink()
            (template / 'fresh.md').write_text('# Fresh\n\nA synthetic page.\n', encoding='utf-8')
            profile = template / 'profile.md'
            profile.write_text(profile.read_text(encoding='utf-8') + '\nA synthetic revision.\n', encoding='utf-8')
            report = review_candidate(template, site, cfg)
            self.assertEqual(report['status'], 'candidate-passed')
            self.assertIn('fresh.html', [row['path'] for row in report['added']])
            self.assertIn('retired.md', [row['path'] for row in report['removed']])
            self.assertIn('profile.html', [row['path'] for row in report['changed']])
            self.assertEqual(original, {str(p): p.read_bytes() for p in site.rglob('*') if p.is_file()})
            self.assertFalse(list(Path(directory).glob('.site-review-*')))
            contact = template / 'contact.md'
            contact.write_text(contact.read_text(encoding='utf-8') + '\n[Wrong](mailto:other@outside.example)\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'quality gate failed'):
                review_candidate(template, site, cfg)
            self.assertEqual(original, {str(p): p.read_bytes() for p in site.rglob('*') if p.is_file()})
            self.assertFalse(list(Path(directory).glob('.site-review-*')))

    def test_search_records_offer_bounded_author_topic_and_page_type_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            (template / 'writing' / 'topic.md').write_text('<!--\ntitle: Topic article\nabout: Research\n-->\n# Topic', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            rows = json.loads((site / 'search-index.json').read_text(encoding='utf-8'))
            article = next(row for row in rows if row['url'] == '/writing/topic.html')
            self.assertEqual(article['type'], 'article')
            self.assertEqual(article['topic_keys'], ['research'])
            core = next(row for row in rows if row['url'] == '/profile.html')
            self.assertEqual(core['type'], 'page')
            self.assertEqual(core['topic_keys'], [])
            page = (site / 'search.html').read_text(encoding='utf-8')
            for text in ('id="topic"', 'value="research"', 'id="page-type"', 'id="search-retry"', '/profile.html'):
                self.assertIn(text, page)
            self.assertFalse(audit(site))

    def test_related_writing_uses_shared_topics_and_excludes_self_and_drafts(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            for slug, topics, status in (('start', 'Research, Publishing', 'published'),
                                         ('match', 'research, Publishing', 'published'),
                                         ('partial', 'Research', 'published'), ('other', 'Cooking', 'published'),
                                         ('secret', 'Research, Publishing', 'draft')):
                (template / 'writing' / (slug + '.md')).write_text(
                    '<!--\ntitle: ' + slug + '\nabout: ' + topics + '\nstatus: ' + status + '\n-->\n# Article', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            output = (site / 'writing' / 'start.html').read_text(encoding='utf-8')
            related = output.split('<nav aria-label="Related writing">', 1)[1].split('</nav>', 1)[0]
            self.assertLess(related.index('/writing/match.html'), related.index('/writing/partial.html'))
            for slug in ('start', 'secret', 'other'):
                self.assertNotIn('/writing/' + slug + '.html', related)
            self.assertIn('Browse all writing', related)
            self.assertFalse(audit(site))

    def test_topic_directory_is_static_stable_and_uses_only_published_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            for slug, status, topics in (('one', 'published', 'Research, <img src=x onerror=bad>'),
                                         ('two', 'published', 'research, Café'), ('secret', 'draft', 'SECRET_TOPIC')):
                (template / 'writing' / (slug + '.md')).write_text(
                    '<!--\nstatus: ' + status + '\ntitle: ' + slug + '\nabout: ' + topics + '\n-->\n# Article', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            output = (site / 'topics.html').read_text(encoding='utf-8')
            self.assertEqual(output.count('id="' + topic_id('Research') + '"'), 1)
            self.assertEqual(topic_id('Research'), topic_id(' research '))
            self.assertEqual(topic_id('Café'), topic_id('Cafe\u0301'))
            self.assertNotIn('<img', output)
            self.assertNotIn('SECRET_TOPIC', output)
            self.assertIn('/writing/one.html', output)
            self.assertIn('/writing/two.html', output)
            self.assertIn('term="Research"', (site / 'feed.xml').read_text(encoding='utf-8'))
            self.assertFalse(audit(site))
            with self.assertRaises(ValueError):
                article_metadata('<!--\nabout: ' + 'x' * 81 + '\n-->')

    def test_archive_orders_declared_dates_and_labels_fallback_without_inventing_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            for slug, dates in (('old', 'published: 2025-01-01\nupdated: 2025-02-01'),
                                ('recent', 'published: 2024-01-01\nupdated: 2025-12-01'),
                                ('undated', '')):
                (template / 'writing' / (slug + '.md')).write_text('<!--\ntitle: ' + slug + '\n' + dates + '\n-->\n# Article', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            rendered = (site / 'writing.html').read_text(encoding='utf-8')
            self.assertLess(rendered.index('/writing/recent.html'), rendered.index('/writing/old.html'))
            self.assertLess(rendered.index('/writing/old.html'), rendered.index('/writing/undated.html'))
            self.assertIn('Site date (fallback)', rendered)
            self.assertIn('datetime="2025-12-01"', rendered)
            feed = ET.parse(site / 'feed.xml')
            ns = {'a': 'http://www.w3.org/2005/Atom'}
            entries = feed.findall('a:entry', ns)
            self.assertEqual(entries[0].findtext('a:title', namespaces=ns), 'recent')
            undated = next(entry for entry in entries if entry.findtext('a:title', namespaces=ns) == 'undated')
            self.assertIsNone(undated.find('a:published', ns))

    def test_character_references_remain_literal_without_hiding_unsafe_urls(self):
        from html.parser import HTMLParser
        class Text(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text, self.links = [], []
            def handle_data(self, data):
                self.text.append(data)
            def handle_starttag(self, tag, attrs):
                if tag == 'a':
                    self.links.append(dict(attrs)['href'])
        source = '&#42;&#42;literal&#42;&#42; &#91;label&#93; &#124; &amp; &lt; `&amp;`'
        parsed = Text()
        parsed.feed(md_to_html(source + ' [bad](java&#115;cript:alert%281%29) [good](https://example.test/a&#95;b)'))
        self.assertIn('**literal** [label] | & < &amp;', ''.join(parsed.text))
        self.assertEqual(parsed.links, ['https://example.test/a_b'])
        self.assertNotIn('<strong>', md_to_html(source))

    def test_core_page_companions_preserve_sources_and_existing_html(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            source = '# Core &amp; notes\n\n## Evidence\nLiteral <img src=x onerror=alert(1)>\n'
            (template / 'notes.md').write_text(source, encoding='utf-8')
            (template / 'custom.md').write_text('# Custom', encoding='utf-8')
            custom = '<!doctype html><html><body>Authored HTML retained</body></html>'
            (template / 'custom.html').write_text(custom, encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            rendered = (site / 'notes.html').read_text(encoding='utf-8')
            self.assertIn('href="/notes.md"', rendered)
            self.assertIn('id="evidence"', rendered)
            self.assertIn('href="#evidence"', rendered)
            self.assertNotIn('<img', rendered)
            self.assertNotIn('application/ld+json', rendered)
            self.assertEqual((site / 'notes.md').read_text(encoding='utf-8'), source)
            self.assertEqual((site / 'custom.html').read_text(encoding='utf-8'), custom)
            records = json.loads((site / 'search-index.json').read_text(encoding='utf-8'))
            self.assertIn('/notes.html', [row['url'] for row in records])
            self.assertIn('/custom.md', [row['url'] for row in records])
            self.assertFalse(audit(site))

    def test_editorial_review_reports_errors_and_draft_work_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            template, _, cfg = self.fixture(directory)
            create_article(directory, 'notes', 'Notes')
            bad = template / 'writing' / 'bad.md'
            bad.write_text('<!--\ntitle: Bad\nupdated: 2026-02-30\n-->\n# Bad', encoding='utf-8')
            before = {str(p): p.read_bytes() for p in template.rglob('*') if p.is_file()}
            report = review_articles(template, cfg)
            self.assertEqual(report['drafts'], 1)
            self.assertEqual(report['errors'], 1)
            draft = next(r for r in report['articles'] if r['status'] == 'draft')
            self.assertIn('add article body before publication', draft['warnings'])
            self.assertGreater(report['publication_warnings'], 0)
            self.assertEqual(before, {str(p): p.read_bytes() for p in template.rglob('*') if p.is_file()})
            self.assertFalse((Path(directory) / 'site').exists())

    def test_article_cli_creates_inert_draft_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            repo = Path(directory)
            shutil.copytree(ROOT / 'scripts', repo / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            title = 'Notes [draft] </script> --> & {{EMAIL}}'
            command = [sys.executable, str(repo / 'scripts' / 'article.py'), 'new', 'field-notes', '--title', title,
                       '--description', 'A bounded summary.', '--topic', 'Research']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            path = template / 'writing' / 'field-notes.md'
            original = path.read_bytes()
            meta, _ = article_metadata(original.decode())
            self.assertEqual(meta['title'], title)
            self.assertEqual(meta['status'], 'draft')
            self.assertNotIn('published', meta)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(path.read_bytes(), original)
            for companion_name in ('existing.html', 'Mixed.HTML', 'Source.MD'):
                companion = template / 'writing' / companion_name
                companion.write_bytes(b'Existing authored bytes')
                slug = companion.stem.lower()
                with self.subTest(companion=companion_name), self.assertRaises(FileExistsError):
                    create_article(repo, slug, 'A new draft')
                self.assertEqual(companion.read_bytes(), b'Existing authored bytes')
                if companion.suffix.lower() == '.html':
                    self.assertFalse((companion.parent / (slug + '.md')).exists())
                companion.unlink()
            build_site_staged(str(template), str(site), cfg)
            self.assertFalse((site / 'writing' / 'field-notes.md').exists())
            for slug in ('../escape', 'Uppercase', 'con', '/absolute', 'a--b'):
                with self.subTest(slug=slug), self.assertRaises(ValueError):
                    create_article(repo, slug, 'Title')
            with self.assertRaises(ValueError):
                create_article(repo, 'other', 'Title\nstatus: published')

    def fixture(self, directory):
        template, site = Path(directory) / 'template', Path(directory) / 'site'
        shutil.copytree(ROOT / 'template', template)
        cfg = json.loads((ROOT / 'site.config.example.json').read_text(encoding='utf-8'))
        return template, site, dict(cfg, **json_block(cfg))

    def test_draft_bytes_never_enter_public_build_and_transitions_remove_them(self):
        sentinel = 'UNPUBLISHED_SYNTHETIC_SENTINEL_63eaf7'
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            path = template / 'writing' / 'pending.md'
            source = '<!--\nstatus: %s\ntitle: Pending\n-->\n# Pending\n' + sentinel
            path.write_text('\ufeff \ufeff\n' + source % 'draft', encoding='utf-8')
            (template / 'writing' / 'pending.html').write_text(sentinel, encoding='utf-8')
            private_folder = template / 'writing' / 'draft-only-folder'
            private_folder.mkdir()
            (private_folder / 'nested.md').write_text(source % 'draft', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            self.assertFalse((site / 'writing' / 'pending.md').exists())
            self.assertFalse((site / 'writing' / 'draft-only-folder').exists())
            for output in site.rglob('*'):
                if output.is_file():
                    self.assertNotIn(sentinel.encode(), output.read_bytes(), str(output))
            path.write_text(source % 'published', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            self.assertIn(sentinel, (site / 'writing' / 'pending.html').read_text(encoding='utf-8'))
            path.write_text(source % 'draft', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            self.assertFalse((site / 'writing' / 'pending.html').exists())

    def test_ambiguous_article_status_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            build_site_staged(str(template), str(site), cfg)
            original = (site / 'content-manifest.json').read_bytes()
            for metadata in ('status: Draft', 'status: draft\nSTATUS: published',
                             'statuz: draft', 'status:', 'status: {{STATUS}}', 'status draft'):
                with self.subTest(metadata=metadata):
                    (template / 'writing' / 'bad.md').write_text('<!--\n' + metadata + '\n-->\n# Bad', encoding='utf-8')
                    with self.assertRaises(ValueError):
                        build_site_staged(str(template), str(site), cfg)
                    self.assertEqual((site / 'content-manifest.json').read_bytes(), original)

    def test_paired_contact_framing_agrees_in_source_and_rendered_prose(self):
        address = "o'hara@yourname.com"
        for marker in ('', '**', '_', '`', '``', '**_'):
            for quote in ("'", '"'):
                source = marker + quote + 'mailto:o%27hara%40yourname.com' + quote + marker[::-1]
                for text, suffix in ((source, '.md'), (md_to_html(source), '.html')):
                    with self.subTest(source=source, suffix=suffix):
                        self.assertEqual(contact_values(text, suffix)[1], [address])

    def test_contact_destination_corruption_is_never_markdown_framing(self):
        for source in ("[Contact](mailto:a@x.example'evil)", "<mailto:a@x.example'evil>",
                       "**'mailto:a@x.example'**evil", "_'mailto:a@x.example'evil'_",
                       "`'mailto:a@x.example'evil'`", "mailto:a@x.example'**"):
            with self.subTest(source=source):
                values = contact_values(source, '.md')[1]
                self.assertTrue(values)
                self.assertNotIn('a@x.example', values)
        self.assertEqual(contact_values('<a href="mailto:a@x.example\'**">Contact</a>', '.html')[1],
                         ["a@x.example'**"])


if __name__ == '__main__':
    unittest.main()
