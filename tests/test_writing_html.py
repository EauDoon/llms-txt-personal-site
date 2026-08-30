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


if __name__ == "__main__":
    unittest.main()
