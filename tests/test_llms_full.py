from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_llms_full import run as build_llms_full


class LlmsFullTests(unittest.TestCase):
    def test_source_url_encodes_custom_markdown_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "custom guide.md").write_text("# Custom guide\n", encoding="utf-8")

            build_llms_full(
                str(site),
                {
                    "DOMAIN": "example.test",
                    "FULL_NAME": "Example Person",
                    "LAST_UPDATED": "2026-08-30",
                },
            )

            output = (site / "llms-full.txt").read_text(encoding="utf-8")
            self.assertIn("# SOURCE: https://example.test/custom%20guide.md", output)
            self.assertNotIn("https://example.test/custom guide.md", output)


if __name__ == "__main__":
    unittest.main()
