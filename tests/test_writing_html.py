from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_writing_html import md_to_html, page_description, run


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

    def test_bare_url_autolink_excludes_sentence_punctuation(self) -> None:
        # A full stop is a legal path character, so a greedy match publishes a
        # destination that resolves nowhere.
        for markdown, expected in (
            ("See https://employer.example.com. Next", '<a href="https://employer.example.com">'),
            ("More https://a.test/b, here", '<a href="https://a.test/b">'),
            ("End https://a.test/b! Now", '<a href="https://a.test/b">'),
            ("Q https://a.test/b? Then", '<a href="https://a.test/b">'),
            ("Semi https://a.test/b; Next", '<a href="https://a.test/b">'),
        ):
            with self.subTest(markdown=markdown):
                self.assertIn(expected, md_to_html(markdown))
                for terminator in ".,;:!?":
                    self.assertNotIn(
                        '<a href="https://a.test/b%s"' % terminator, md_to_html(markdown)
                    )

    def test_bare_url_autolink_keeps_interior_path_characters(self) -> None:
        rendered = md_to_html("Path https://a.test/x.b/c?d=1. done")

        self.assertIn('<a href="https://a.test/x.b/c?d=1">', rendered)
        self.assertIn("</a>. done", rendered)

    def test_balanced_parentheses_stay_in_link_destinations(self) -> None:
        # Wikipedia-style paths are legal URLs. Stopping at the first ")"
        # publishes a destination that does not exist.
        rendered = md_to_html(
            "See [wiki](https://en.wikipedia.org/wiki/Foo_(bar)).\n\n"
            "Bare https://en.wikipedia.org/wiki/Foo_(bar)."
        )

        self.assertEqual(rendered.count('href="https://en.wikipedia.org/wiki/Foo_(bar)"'), 2)
        self.assertNotIn('href="https://en.wikipedia.org/wiki/Foo_(bar"', rendered)
        self.assertIn("</a>.", rendered)
        wrapped = md_to_html("(see https://example.com/a).")
        self.assertIn('href="https://example.com/a"', wrapped)
        self.assertNotIn('href="https://example.com/a)"', wrapped)

    def test_angle_bracket_url_inside_a_markdown_link_stays_one_anchor(self) -> None:
        # The autolinker runs on text that is already an anchor. A label or
        # destination written as <https://...> is escaped to &lt;...&gt; and
        # then wrapped in a second anchor, so the markup is no longer HTML.
        label = md_to_html("[see <https://example.com/a>](https://example.com/b)")
        self.assertEqual(
            label,
            '<p><a href="https://example.com/b">see &lt;https://example.com/a&gt;</a></p>',
        )
        destination = md_to_html("[Docs](<https://example.com/a>)")
        self.assertEqual(
            destination,
            '<p><a href="https://example.com/a">Docs</a></p>',
        )

    def test_angle_bracket_urls_do_not_include_the_escaped_closer(self) -> None:
        # The source is escaped before autolinking, so <https://example.com/a>
        # becomes a destination of https://example.com/a&gt and the semicolon
        # is left behind as sentence punctuation.
        rendered = md_to_html("See <https://example.com/a>.")
        self.assertIn('<a href="https://example.com/a">https://example.com/a</a>.', rendered)
        self.assertNotIn("&gt", rendered)
        self.assertNotIn("&lt;", rendered)
        paren = md_to_html("See <https://en.wikipedia.org/wiki/Foo_(bar)>.")
        self.assertIn('href="https://en.wikipedia.org/wiki/Foo_(bar)"', paren)
        self.assertNotIn("&gt", paren)

    def test_closing_fence_may_have_trailing_whitespace(self) -> None:
        # A closing fence is backticks and nothing else, but CommonMark allows
        # spaces or a tab after them. Leaving those on the line keeps the fence
        # open, so the rest of the page is published as code.
        rendered = md_to_html("```\ncode\n``` \nAfter the fence.\n")
        self.assertEqual(rendered, "<pre><code>code</code></pre>\n<p>After the fence.</p>")
        tabbed = md_to_html("```python\ncode\n```\t\nAfter the fence.\n")
        self.assertEqual(
            tabbed,
            '<pre><code class="language-python">code</code></pre>\n<p>After the fence.</p>',
        )
        self.assertNotIn("After the fence.", rendered.split("</code>")[0])

    def test_four_space_backtick_line_stays_inside_the_fence(self) -> None:
        # A closer may be indented by at most three spaces. Four spaces is
        # sample content; treating it as a closer renders the rest as prose.
        rendered = md_to_html("```\nline\n    ```\nstill code\n```\n")
        self.assertEqual(rendered, "<pre><code>line\n    ```\nstill code</code></pre>")
        listed = md_to_html("- item\n  ```text\n<!-- literal -->\n  ```\nAfter\n")
        self.assertIn('<pre><code class="language-text">&lt;!-- literal --&gt;</code></pre>', listed)
        self.assertIn("<p>After</p>", listed)
        self.assertNotIn("<!-- literal -->", listed)

    def test_page_description_stops_at_the_first_sentence(self) -> None:
        # A domain or email contains a period that is not the end of the
        # sentence. The following sentence must not be published as the
        # description of the page.
        rendered = (
            "Title\n"
            "you@yourname.com is the only confirmed address. Any other address is not."
        )
        self.assertEqual(
            page_description(rendered),
            "you@yourname.com is the only confirmed address.",
        )
        self.assertEqual(page_description("Title\nLast updated: 2026-01-01\nOne fact. Another fact."), "One fact.")

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
