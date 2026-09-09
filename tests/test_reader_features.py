import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build import validate_public_contacts
from build_writing_html import render_page

CFG = {"DOMAIN": "example.test", "FULL_NAME": "Example Person", "EMAIL": "person@example.test",
       "EMPLOYER_URL": "https://example.test", "LINKEDIN_SLUG": "example-person",
       "X_HANDLE": "example_person", "LAST_UPDATED": "2026-01-01", "JOB_TITLE": "Writer"}


class ReaderFeatures(unittest.TestCase):
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
