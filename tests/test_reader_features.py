import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build import validate_public_contacts
from build_writing_html import render_page, md_to_html
from build_catalog import run as build_catalog
from build_inventory import run as build_inventory, inventory
from build import build_site_staged
from unittest.mock import patch
from check_artifacts import audit
from xml.etree import ElementTree as ET

CFG = {"DOMAIN": "example.test", "FULL_NAME": "Example Person", "EMAIL": "person@example.test",
       "EMPLOYER_URL": "https://example.test", "LINKEDIN_SLUG": "example-person",
       "X_HANDLE": "example_person", "LAST_UPDATED": "2026-01-01", "JOB_TITLE": "Writer"}


class ReaderFeatures(unittest.TestCase):
    def test_feed_escapes_metadata_and_omits_unknown_publication_date(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'writing').mkdir()
            (root / 'writing' / 'article.md').write_text('<!--\ntitle: <Sample> & notes\nupdated: 2025-12-20\n-->\n# Article', encoding='utf-8')
            build_catalog(root, CFG)
            feed = ET.fromstring((root / 'feed.xml').read_bytes())
            ns = {'a': 'http://www.w3.org/2005/Atom'}
            self.assertEqual(feed.find('a:entry/a:title', ns).text, '<Sample> & notes')
            self.assertEqual(feed.find('a:entry/a:updated', ns).text, '2025-12-20T00:00:00Z')
            self.assertIsNone(feed.find('a:entry/a:published', ns))

    def test_artifact_audit_rejects_active_html_and_malformed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('<script src="data:text/javascript,alert(1)"></script><p onclick="evil">Text</p>', encoding='utf-8')
            build_inventory(root, CFG)
            errors = '\n'.join(audit(root))
            self.assertIn('data URL', errors)
            self.assertIn('event-handler', errors)
            (root / 'content-manifest.json').write_text('[]', encoding='utf-8')
            self.assertIn('must be an object', audit(root)[0])

    def test_artifact_audit_checks_fragments_links_and_current_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'index.html'
            path.write_text('<h1 id="hello">Hello</h1><a href="#hello">Jump</a>', encoding='utf-8')
            build_inventory(root, CFG)
            self.assertEqual(audit(root), [])
            path.write_text('<a href="/missing.html">Broken</a><a href="#absent">Jump</a>', encoding='utf-8')
            errors = '\n'.join(audit(root))
            self.assertIn('inventory differs', errors)
            self.assertIn('missing local target', errors)
            self.assertIn('missing local fragment', errors)

    def test_inventory_is_deterministic_and_detects_byte_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('Example', encoding='utf-8')
            build_inventory(root, CFG)
            first = (root / 'content-manifest.json').read_bytes()
            build_inventory(root, CFG)
            self.assertEqual(first, (root / 'content-manifest.json').read_bytes())
            (root / 'index.html').write_text('Changed', encoding='utf-8')
            self.assertNotEqual(json.loads(first)['files'], inventory(root))
            with patch('build_inventory.MAX_FILE_BYTES', 1), self.assertRaises(ValueError):
                inventory(root)

    def test_build_cannot_replace_or_publish_its_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for output in (root, root / 'site'):
                with self.assertRaisesRegex(ValueError, 'overlap'):
                    build_site_staged(str(root), str(output), CFG)

    def test_publication_dates_are_explicit_and_calendar_valid(self):
        page = render_page('test', '# Example', CFG)
        self.assertNotIn('datePublished', page)
        page = render_page('test', '<!--\npublished: 2025-12-01\nupdated: 2025-12-20\n-->\n# Example', CFG)
        self.assertIn('"datePublished": "2025-12-01"', page)
        self.assertIn('"dateModified": "2025-12-20"', page)
        with self.assertRaises(ValueError):
            render_page('test', '<!--\npublished: 2026-02-30\n-->\n# Example', CFG)
        with self.assertRaises(ValueError):
            render_page('test', '<!--\npublished: 2026-02-01\n-->\n# Example', CFG)

    def test_search_indexes_published_text_without_author_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'profile.md').write_text('# Example\n<!-- do not publish guidance -->\nVerified words', encoding='utf-8')
            build_catalog(root, CFG)
            records = json.loads((root / 'search-index.json').read_text())
            self.assertEqual(records[0]['url'], '/profile.md')
            self.assertIn('Verified words', records[0]['text'])
            self.assertNotIn('guidance', records[0]['text'])
            self.assertIn('/profile.md', (root / 'search.html').read_text())

    def test_writing_directory_tracks_sources_and_empty_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_catalog(root, CFG)
            self.assertIn('No writing pages', (root / 'writing.html').read_text())
            (root / 'writing').mkdir()
            (root / 'writing' / 'a & b.md').write_text('<!--\ntitle: <New>\ndesc: Real description\nabout: Topic\n-->\n# Article', encoding='utf-8')
            build_catalog(root, CFG)
            page = (root / 'writing.html').read_text(encoding='utf-8')
            self.assertIn('a%20%26%20b.html', page)
            self.assertIn('&lt;New&gt;', page)
            self.assertIn('Real description', page)

    def test_outline_has_unique_working_fragments(self):
        page = render_page('test', '# Test\n## Evidence\n## Evidence\n## Main content\n```\n## Hidden\n```', CFG)
        for identifier in ('evidence', 'evidence-2', 'main-content-2'):
            self.assertIn('href="#%s"' % identifier, page)
            self.assertIn('id="%s"' % identifier, page)
        self.assertNotIn('href="#hidden"', page)
        self.assertIn('<main id="main-content">', page)

    def test_fences_are_literal_and_unclosed_fences_terminate(self):
        source = '```html\n<!-- visible -->\n<script>bad()</script>\n[link](https://example.test)\n```\n<!-- hidden -->'
        page = md_to_html(source)
        self.assertIn('&lt;!-- visible --&gt;', page)
        self.assertNotIn('hidden', page)
        self.assertNotIn('<script>', page)
        self.assertNotIn('<a ', page)
        self.assertIn('<pre><code>tail</code></pre>', md_to_html('```\ntail'))

    def test_article_metadata_cannot_terminate_script_or_attribute(self):
        attack = '</script><script>alert(1)</script>'
        page = render_page("test", '<!--\ntitle: ' + attack + '\n-->\n# Test',
                           {**CFG, "FULL_NAME": attack, "EMAIL": 'x" onclick="evil'})
        self.assertEqual(page.count("</script>"), 1)
        self.assertNotIn(' onclick="', page)
        import re
        metadata = json.loads(re.search(r'application/ld\+json">(.*?)</script>', page, re.S)[1])
        self.assertEqual(metadata["headline"], attack)

    def test_contact_routes_are_validated(self):
        validate_public_contacts(CFG)
        for key, value in (("EMPLOYER_URL", "javascript:alert(1)"),
                           ("EMPLOYER_URL", "https://user:pass@example.test"),
                           ("EMAIL", 'person@example.test" onclick="evil'),
                           ("X_HANDLE", "person?other"), ("LINKEDIN_SLUG", "../other")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_public_contacts({**CFG, key: value})


if __name__ == "__main__":
    unittest.main()
