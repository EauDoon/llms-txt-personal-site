import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build import validate_public_contacts
from build_writing_html import render_page, md_to_html
from build_catalog import run as build_catalog

CFG = {"DOMAIN": "example.test", "FULL_NAME": "Example Person", "EMAIL": "person@example.test",
       "EMPLOYER_URL": "https://example.test", "LINKEDIN_SLUG": "example-person",
       "X_HANDLE": "example_person", "LAST_UPDATED": "2026-01-01", "JOB_TITLE": "Writer"}


class ReaderFeatures(unittest.TestCase):
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
