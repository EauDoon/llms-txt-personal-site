from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_writing_html import md_to_html, run


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
            r"\//outside.example/path",
            r"/\outside.example/path",
            r"folder\page.md",
            "javascript:https://safe.example/path",
        ):
            with self.subTest(target=target):
                rendered = md_to_html("[<unsafe> & link](%s)" % target)
                self.assertNotIn("<a href=", rendered)
                self.assertIn("&lt;unsafe&gt; &amp; link", rendered)

    def test_unsafe_markdown_link_text_is_not_autolinked(self) -> None:
        for markdown in (
            "[label](javascript:https://safe.example/path)",
            "[https://safe.example/path](javascript:alert%281%29)",
        ):
            with self.subTest(markdown=markdown):
                rendered = md_to_html(markdown)
                self.assertNotIn("<a href=", rendered)
                self.assertIn("https://safe.example/path", rendered)

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

    def test_writing_index_is_generated_from_markdown_not_edited_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            writing = site / "writing"
            writing.mkdir()
            (writing / "signed-work.md").write_text(
                "<!--\ntitle: Signed Work\n-->\n\n# Signed Work\n",
                encoding="utf-8",
            )
            (site / "index.html").write_text(
                "<h2>Writing</h2>\n"
                "<!-- BEGIN GENERATED WRITING INDEX -->\n"
                "<ul><li><a href=\"/writing/example-depth-page.html\">"
                "Example depth page</a></li></ul>\n"
                "<!-- END GENERATED WRITING INDEX -->\n",
                encoding="utf-8",
            )

            run(
                str(site),
                {
                    "DOMAIN": "person.example",
                    "FULL_NAME": "Signed Person",
                    "EMAIL": "signed@person.example",
                    "LAST_UPDATED": "2026-08-31",
                    "JOB_TITLE": "Signed Role",
                },
            )

            index = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn(
                '<a href="/writing/signed-work.html">Signed Work</a>',
                index,
            )
            self.assertNotIn("example-depth-page", index)


if __name__ == "__main__":
    unittest.main()
