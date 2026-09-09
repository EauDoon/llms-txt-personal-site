"""Integrated editorial and reader contracts for the static publisher."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build import build_site_staged, json_block
from build_writing_html import md_to_html
from email_addresses import contact_values


class PublishingTests(unittest.TestCase):
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
