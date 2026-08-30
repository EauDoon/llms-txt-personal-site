from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_writing_html import md_to_html


class WritingHtmlTests(unittest.TestCase):
    def test_unmatched_block_prefixes_render_as_literal_paragraphs(self) -> None:
        rendered = md_to_html("| not a table\n>not a quote\n# Next section")

        self.assertEqual(
            rendered,
            "<p>| not a table</p>\n<p>&gt;not a quote</p>\n<h1>Next section</h1>",
        )

    def test_active_and_ambiguous_markdown_links_render_inert(self) -> None:
        for target in (
            "JaVaScRiPt:alert%281%29",
            " \tjavascript:alert%281%29",
            "java\tscript:alert%281%29",
            "data:text/html,payload",
            "vbscript:msgbox%281%29",
            "file:///private.txt",
            "//other.example/path",
            "\\\\other.example\\path",
        ):
            with self.subTest(target=target):
                rendered = md_to_html("[<unsafe> & link](%s)" % target)
                self.assertNotIn("<a href=", rendered)
                self.assertIn("&lt;unsafe&gt; &amp; link", rendered)

    def test_relative_and_explicit_safe_markdown_links_remain_links(self) -> None:
        for target in (
            "../about.md",
            "/profile.md",
            "#evidence",
            "http://example.test/path",
            "HTTPS://example.test/path?x=1&y=2",
            "mailto:person%40example.test",
        ):
            with self.subTest(target=target):
                rendered = md_to_html("[<safe> & link](%s)" % target)
                self.assertIn("<a href=", rendered)
                self.assertIn("&lt;safe&gt; &amp; link", rendered)
        self.assertIn(
            'href="HTTPS://example.test/path?x=1&amp;y=2"',
            md_to_html("[query](HTTPS://example.test/path?x=1&y=2)"),
        )


if __name__ == "__main__":
    unittest.main()
