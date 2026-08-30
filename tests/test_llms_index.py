from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_llms_index import MARKER, run as build_llms_index


class LlmsIndexTests(unittest.TestCase):
    def test_writing_pages_are_indexed_with_encoded_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            writing = site / "writing"
            writing.mkdir()
            (site / "llms.txt").write_text(
                "# Example\n\n%s\n\n## Optional\n\n- [Full](https://example.test/llms-full.txt)\n"
                % MARKER,
                encoding="utf-8",
            )
            (writing / "agent guide.md").write_text(
                """<!--
title: Agent [guide]
desc: A concise writing page.
-->
# Agent guide
""",
                encoding="utf-8",
            )

            count = build_llms_index(site, {"DOMAIN": "example.test"})
            output = (site / "llms.txt").read_text(encoding="utf-8")

        self.assertEqual(count, 1)
        self.assertIn("## Writing", output)
        self.assertIn("Agent &#91;guide&#93;", output)
        self.assertIn("https://example.test/writing/agent%20guide.md", output)
        self.assertIn(": A concise writing page.", output)
        self.assertNotIn(MARKER, output)

    def test_empty_writing_directory_does_not_leave_an_empty_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "writing").mkdir()
            (site / "llms.txt").write_text(
                "# Example\n\n%s\n\n## Optional\n\n- [Full](https://example.test/llms-full.txt)\n"
                % MARKER,
                encoding="utf-8",
            )

            count = build_llms_index(site, {"DOMAIN": "example.test"})
            output = (site / "llms.txt").read_text(encoding="utf-8")

        self.assertEqual(count, 0)
        self.assertNotIn("## Writing", output)
        self.assertNotIn(MARKER, output)

    def test_missing_marker_fails_instead_of_silently_omitting_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "llms.txt").write_text("# Example\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "exactly one"):
                build_llms_index(site, {"DOMAIN": "example.test"})


if __name__ == "__main__":
    unittest.main()
