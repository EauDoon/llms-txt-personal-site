from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build import build_site_staged, load_config
from build_llms_full import run as build_llms_full
from build_sitemap import validate_last_updated
from build_writing_html import md_to_html, run as build_writing_html


class BuildTests(unittest.TestCase):
    def test_llms_full_includes_custom_top_level_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "profile.md").write_text("# Profile\n", encoding="utf-8")
            (site / "custom.md").write_text("# Custom\n", encoding="utf-8")
            (site / "changelog.md").write_text("# Changelog\n", encoding="utf-8")

            names = build_llms_full(str(site), self.config())

            self.assertEqual(names, ["profile.md", "custom.md", "changelog.md"])
            self.assertIn(
                "# Custom",
                (site / "llms-full.txt").read_text(encoding="utf-8"),
            )

    def config(self, last_updated: str = "2026-08-29") -> dict[str, str]:
        return {
            "DOMAIN": "example.test",
            "FULL_NAME": "Example Person",
            "EMAIL": "person@example.test",
            "JOB_TITLE": "Example Role",
            "LAST_UPDATED": last_updated,
        }

    def test_staged_rebuild_removes_renamed_and_deleted_template_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            writing = template / "writing"
            writing.mkdir(parents=True)
            (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")
            retired = template / "retired.md"
            retired.write_text("# Retired\n\nLast updated: {{LAST_UPDATED}}\n", encoding="utf-8")
            old_article = writing / "old-article.md"
            old_article.write_text("# Old article\n\nLast updated: {{LAST_UPDATED}}\n", encoding="utf-8")
            site = root / "site"

            build_site_staged(str(template), str(site), self.config())
            self.assertTrue((site / "retired.md").is_file())
            self.assertTrue((site / "writing" / "old-article.html").is_file())
            self.assertIn("/writing/old-article.html", (site / "sitemap.xml").read_text(encoding="utf-8"))

            retired.unlink()
            old_article.rename(writing / "new-article.md")
            build_site_staged(str(template), str(site), self.config())

            self.assertFalse((site / "retired.md").exists())
            self.assertFalse((site / "writing" / "old-article.md").exists())
            self.assertFalse((site / "writing" / "old-article.html").exists())
            self.assertTrue((site / "writing" / "new-article.md").is_file())
            self.assertTrue((site / "writing" / "new-article.html").is_file())
            sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
            self.assertNotIn("retired.md", sitemap)
            self.assertNotIn("old-article", sitemap)
            self.assertIn("/writing/new-article.md", sitemap)
            self.assertIn("/writing/new-article.html", sitemap)
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    def test_failed_staged_generation_preserves_previous_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")
            site = root / "site"
            build_site_staged(str(template), str(site), self.config())
            before = (site / "sitemap.xml").read_bytes()

            with self.assertRaisesRegex(ValueError, "calendar-valid"):
                build_site_staged(str(template), str(site), self.config("2026-02-30"))

            self.assertEqual((site / "sitemap.xml").read_bytes(), before)
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    def test_locked_backup_cleanup_warns_after_successful_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text("<h1>New site</h1>\n", encoding="utf-8")
            site = root / "site"
            site.mkdir()
            (site / "stale.txt").write_text("old site\n", encoding="utf-8")
            error = io.StringIO()

            with patch("build.shutil.rmtree", side_effect=PermissionError("locked by scanner")):
                with contextlib.redirect_stderr(error):
                    build_site_staged(str(template), str(site), self.config())

            self.assertEqual((site / "index.html").read_text(encoding="utf-8"), "<h1>New site</h1>\n")
            self.assertFalse((site / "stale.txt").exists())
            backups = list(root.glob(".site-backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "stale.txt").read_text(encoding="utf-8"), "old site\n")
            self.assertIn("new site was promoted", error.getvalue())
            self.assertIn("previous output could not be removed", error.getvalue())
            self.assertIn("locked by scanner", error.getvalue())

    def test_last_updated_requires_an_exact_calendar_date(self) -> None:
        self.assertEqual(validate_last_updated("2024-02-29"), "2024-02-29")
        for value in ("", "2026-02-29", "2026-02-30", "20260829", "2026-8-29", None, 20260829):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "calendar-valid"):
                    validate_last_updated(value)

    def test_domain_must_be_a_bare_hostname(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "site.config.json"
            for domain in (
                "HTTPS://example.test",
                "example.test/path",
                "user@example.test",
                "example.test:443",
                "example..test",
                "-example.test",
                "example-.test",
                "example\\test",
                'example"test',
                "café.test",
                f"{'a' * 64}.test",
            ):
                config_path.write_text(json.dumps({**self.config(), "DOMAIN": domain}), encoding="utf-8")
                with self.subTest(domain=domain), patch("build.CONFIG", str(config_path)):
                    with self.assertRaisesRegex(SystemExit, "bare hostname"):
                        load_config()
            for domain in ("EXAMPLE.TEST", "xn--caf-dma.test"):
                config_path.write_text(json.dumps({**self.config(), "DOMAIN": domain}), encoding="utf-8")
                with self.subTest(domain=domain), patch("build.CONFIG", str(config_path)):
                    self.assertEqual(load_config()["DOMAIN"], domain)

    def test_markdown_link_cannot_inject_html_attributes(self) -> None:
        rendered = md_to_html(
            '[safe](https://example.test/" onmouseover="document.body.dataset.pwned=\'yes\')'
        )

        self.assertNotIn(' onmouseover="', rendered)
        self.assertIn("&quot;", rendered)

    def test_writing_filename_cannot_inject_html_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            writing = site / "writing"
            writing.mkdir()
            slug = 'bad" onmouseover="alert(1)'
            (writing / f"{slug}.md").write_text("# Test\n", encoding="utf-8")

            build_writing_html(str(site), self.config())

            rendered = (writing / f"{slug}.html").read_text(encoding="utf-8")
            self.assertNotIn(' onmouseover="', rendered)
            self.assertIn("bad%22%20onmouseover%3D%22alert%281%29.html", rendered)


if __name__ == "__main__":
    unittest.main()
