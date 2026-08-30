from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QualityCheckTests(unittest.TestCase):
    def run_quality_check(self, writing_as_file: bool = False) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            scripts = repo / "scripts"
            scripts.mkdir()
            shutil.copy2(ROOT / "scripts" / "build_sitemap.py", scripts)
            shutil.copy2(ROOT / "scripts" / "llms_txt.py", scripts)
            shutil.copy2(ROOT / "scripts" / "quality_check.py", scripts)

            site = repo / "site"
            site.mkdir()
            (site / "index.html").write_text(
                '<!doctype html>\n'
                '<link rel="alternate" type="text/markdown" href="/profile.md">\n'
                '<link rel="describedby" href="/llms.txt">\n',
                encoding="utf-8",
            )
            (site / "profile.md").write_text(
                "# Example profile\n\nLast updated: 2026-08-30\n",
                encoding="utf-8",
            )
            (site / "llms.txt").write_text(
                "# Example\n\n"
                "## Start here\n\n"
                "- [Profile](https://example.test/profile.md): Canonical profile.\n",
                encoding="utf-8",
            )
            (site / "sitemap.xml").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                "  <url>\n"
                "    <loc>https://example.test/</loc>\n"
                "    <lastmod>2026-08-30</lastmod>\n"
                "  </url>\n"
                "  <url>\n"
                "    <loc>https://example.test/llms.txt</loc>\n"
                "    <lastmod>2026-08-30</lastmod>\n"
                "  </url>\n"
                "  <url>\n"
                "    <loc>https://example.test/profile.md</loc>\n"
                "    <lastmod>2026-08-30</lastmod>\n"
                "  </url>\n"
                "</urlset>\n",
                encoding="utf-8",
            )
            if writing_as_file:
                (site / "writing").write_text("not a directory\n", encoding="utf-8")

            (repo / "site.config.json").write_text(
                json.dumps({"DOMAIN": "example.test", "LAST_UPDATED": "2026-08-30"}),
                encoding="utf-8",
            )

            return subprocess.run(
                [sys.executable, str(scripts / "quality_check.py")],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_site_without_writing_directory_passes_quality_check(self) -> None:
        result = self.run_quality_check()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_non_directory_writing_path_does_not_crash_quality_check(self) -> None:
        result = self.run_quality_check(writing_as_file=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
