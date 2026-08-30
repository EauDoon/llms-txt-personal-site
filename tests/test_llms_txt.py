from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from llms_txt import has_link_relation, markdown_alternate, validate_llms_txt
from build_writing_html import render_page


class LlmsTxtTests(unittest.TestCase):
    def test_v2_file_lists_and_local_artifacts_validate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "profile.md").write_text("# Profile\n", encoding="utf-8")
            text = """# Example

> A concise guide.

Use dated claims.

## Start here

- [Profile](https://example.test/profile.md): Canonical facts.
- [External](https://outside.test/guide.md): Useful context.
"""

            self.assertEqual(validate_llms_txt(text, "example.test", site), [])

    def test_non_link_sections_and_insecure_links_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            issues = validate_llms_txt(
                """# Example

## Pages

- Bare fact: not a file link
- [Missing](http://example.test/missing.md)
""",
                "example.test",
                directory,
            )

        self.assertTrue(any("file-list item" in issue for issue in issues))
        self.assertTrue(any("absolute HTTPS" in issue for issue in issues))

    def test_duplicate_links_and_non_file_local_links_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "profile.md").write_text("# Profile\n", encoding="utf-8")
            issues = validate_llms_txt(
                """# Example

## Pages

- [Profile](https://example.test/profile.md)
- [Profile again](https://example.test/profile.md)
- [Homepage](https://example.test/)
""",
                "example.test",
                site,
            )

        self.assertTrue(any("repeats URL" in issue for issue in issues))
        self.assertTrue(any("LLM-friendly" in issue for issue in issues))

    def test_same_site_links_stay_in_the_build_and_use_the_canonical_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "profile.md").write_text("# Profile\n", encoding="utf-8")
            issues = validate_llms_txt(
                """# Example

## Pages

- [Credentials](https://user@example.test/profile.md)
- [Port](https://example.test:444/profile.md)
- [Traversal](https://example.test/%2e%2e/private.md)
- [Drive](https://example.test/D:/outside.md)
- [Missing](https://example.test/missing.md)
- [Query](https://example.test/profile.md?view=full)
""",
                "example.test",
                site,
            )

        self.assertTrue(any("credentials" in issue for issue in issues))
        self.assertTrue(any("canonical HTTPS origin" in issue for issue in issues))
        self.assertGreaterEqual(
            sum("invalid same-site path" in issue for issue in issues),
            2,
        )
        self.assertTrue(any("missing build artifact" in issue for issue in issues))
        self.assertTrue(any("link directly" in issue for issue in issues))

    def test_markdown_alternate_encodes_filesystem_names_as_urls(self) -> None:
        self.assertEqual(markdown_alternate("index.html"), "/profile.md")
        self.assertEqual(
            markdown_alternate("writing/agent guide.html"),
            "/writing/agent%20guide.md",
        )
        self.assertEqual(
            markdown_alternate("writing/caf\u00e9.html"),
            "/writing/caf%C3%A9.md",
        )
        document = render_page(
            "agent guide",
            "# Agent guide\n",
            {
                "DOMAIN": "example.test",
                "FULL_NAME": "Example Person",
                "EMAIL": "person@example.test",
                "JOB_TITLE": "Example Role",
                "LAST_UPDATED": "2026-08-30",
            },
        )
        self.assertTrue(
            has_link_relation(
                document,
                "alternate",
                markdown_alternate("writing/agent guide.html"),
                "text/markdown",
            )
        )

    def test_only_h1_and_h2_headings_are_accepted(self) -> None:
        issues = validate_llms_txt("# Example\n\n### Too deep\n")

        self.assertTrue(any("uses H3" in issue for issue in issues))

    def test_html_link_relations_are_parsed_by_attribute_value(self) -> None:
        document = """<html><head>
<link href="/llms.txt" rel="help describedby">
<link type="text/markdown" href="/profile.md" rel="alternate">
</head></html>"""

        self.assertTrue(has_link_relation(document, "describedby", "/llms.txt"))
        self.assertTrue(
            has_link_relation(document, "alternate", "/profile.md", "text/markdown")
        )
        self.assertFalse(
            has_link_relation(document, "alternate", "/profile.md", "text/plain")
        )

    def test_host_configs_advertise_the_covering_llms_file(self) -> None:
        marker = "</llms.txt>; rel=describedby"
        for name in ("_headers", "vercel.json", ".htaccess"):
            with self.subTest(name=name):
                self.assertIn(
                    marker,
                    (ROOT / "template" / name).read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
