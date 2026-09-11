"""Author and reader workflow regressions using synthetic content."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from article import create_article
from publishing import review_articles
from build_catalog import run as catalog
from build_writing_html import render_page


class WorkflowTests(unittest.TestCase):
    def test_duplicate_title_report_keeps_each_finding_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'writing').mkdir()
            for i in range(20):
                (root / 'writing' / ('note-%d.md' % i)).write_text('<!--\ntitle: Notes\n-->\n# Notes\nBody', encoding='utf-8')
            report = review_articles(root, {'LAST_UPDATED': '2026-01-01'})
            for row in report['articles']:
                warning = next(w for w in row['warnings'] if 'duplicate title' in w)
                self.assertLess(len(warning), 300)
                self.assertIn('20 articles', warning)

    def test_search_inventory_exposes_authored_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'writing').mkdir()
            (root / 'writing/notes.md').write_text('<!--\ntitle: Notes\ndesc: Methods summary\nabout: Research\n-->\n# Notes', encoding='utf-8')
            catalog(root, {'FULL_NAME': 'Example', 'LAST_UPDATED': '2026-01-01', 'DOMAIN': 'example.test'})
            row = json.loads((root / 'search-index.json').read_text(encoding='utf-8'))[0]
            self.assertEqual(row['description'], 'Methods summary')
            self.assertEqual(row['topics'], ['Research'])

    def test_feed_includes_inert_full_text_and_discoverable_subscription(self):
        cfg = {'FULL_NAME': 'Example', 'DOMAIN': 'example.test', 'LAST_UPDATED': '2026-01-01'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'writing').mkdir()
            source = '# Notes\n\nRead <script> safely.\n<!-- secret guidance -->'
            (root / 'writing/notes.md').write_text(source, encoding='utf-8')
            catalog(root, cfg)
            feed = ET.fromstring((root / 'feed.xml').read_bytes())
            content = feed.find('{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}content')
            self.assertIsNotNone(content)
            self.assertEqual(content.attrib['type'], 'text')
            self.assertIn('Read <script> safely.', content.text)
            self.assertNotIn('secret guidance', content.text)
            self.assertFalse(list(content))
            for document in ((root / 'writing.html').read_text(encoding='utf-8'), render_page('notes', source, cfg)):
                self.assertIn('type="application/atom+xml"', document)
                self.assertIn('href="/feed.xml">Subscribe', document)

    def test_reading_estimate_uses_visible_body_in_directory_and_article(self):
        cfg = {'FULL_NAME': 'Example', 'DOMAIN': 'example.test', 'LAST_UPDATED': '2026-01-01'}
        body = '# Notes\n\n' + 'word ' * 440 + '\n<!-- ' + 'hidden ' * 1000 + '-->'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'writing').mkdir()
            (root / 'writing/notes.md').write_text(body, encoding='utf-8')
            catalog(root, cfg)
            self.assertIn('About 3 min read', (root / 'writing.html').read_text(encoding='utf-8'))
            self.assertIn('About 3 min read', render_page('notes', body, cfg))
            self.assertIn('About 1 min read', render_page('short', '# Short', cfg))

    def test_review_identifies_ambiguous_titles_without_changing_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'writing').mkdir()
            sources = {'one': '<!--\ntitle: Café\n-->\n# Different\nBody',
                       'two': '<!--\ntitle: CAFÉ\nstatus: draft\n-->\n# Café\nBody'}
            for slug, source in sources.items():
                (root / 'writing' / (slug + '.md')).write_text(source, encoding='utf-8')
            report = review_articles(root, {'LAST_UPDATED': '2026-01-01'})
            for row in report['articles']:
                self.assertTrue(any('duplicate title' in warning for warning in row['warnings']))
            self.assertTrue(any('heading differs' in w for w in report['articles'][0]['warnings']))
            self.assertFalse(any('heading differs' in w for w in report['articles'][1]['warnings']))
            for slug, source in sources.items():
                self.assertEqual((root / 'writing' / (slug + '.md')).read_text(encoding='utf-8'), source)

    def test_new_article_accepts_only_valid_explicit_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'template').mkdir()
            target = create_article(root, 'dated', 'Dated', published='2026-01-01', updated='2026-02-01')
            text = target.read_text(encoding='utf-8')
            self.assertIn('published: 2026-01-01', text)
            self.assertIn('updated: 2026-02-01', text)
            self.assertIn('status: draft', text)
            for options in ({'published': '2026-02-30'}, {'updated': 'tomorrow'},
                            {'published': '2026-02-02', 'updated': '2026-02-01'}):
                with self.assertRaises(ValueError):
                    create_article(root, 'invalid', 'Invalid', **options)
            self.assertFalse((root / 'template/writing/invalid.md').exists())

    def test_import_body_preserves_source_and_stays_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'template').mkdir()
            source = root / 'notes.md'
            source.write_text('# Imported\n\nCafé notes.\n', encoding='utf-8')
            target = create_article(root, 'notes', 'Notes', body_path=source)
            self.assertIn('status: draft', target.read_text(encoding='utf-8'))
            self.assertTrue(target.read_text(encoding='utf-8').endswith(source.read_text(encoding='utf-8')))
            with self.assertRaises(FileExistsError):
                create_article(root, 'notes', 'Notes', body_path=source)
            source.write_text('<!--\nstatus: published\n-->\n# Unsafe metadata', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'metadata'):
                create_article(root, 'other', 'Other', body_path=source)
            self.assertFalse((root / 'template/writing/other.md').exists())


if __name__ == '__main__':
    unittest.main()
