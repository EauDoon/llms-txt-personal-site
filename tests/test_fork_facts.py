"""Regressions for configured facts and article dates a real fork supplies."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from article import create_article
from build import build_site_staged, fill, json_block
from publishing import review_articles


def config(**changes):
    cfg = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))
    cfg.update(changes)
    return cfg


class QuotedFactTests(unittest.TestCase):
    NAME = "Aoife O'Brien"
    EMPLOYER = 'Smith "Widgets" & Sons'

    def test_markdown_and_text_keep_apostrophes_and_quotes_literal(self) -> None:
        cfg = config(FULL_NAME=self.NAME, FAMILY_NAME="O'Brien", EMPLOYER=self.EMPLOYER)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "template", root / "template")
            build_site_staged(str(root / "template"), str(root / "site"), dict(cfg, **json_block(cfg)))
            site = root / "site"
            llms = (site / "llms.txt").read_text(encoding="utf-8")
            profile = (site / "profile.md").read_text(encoding="utf-8")
            full = (site / "llms-full.txt").read_text(encoding="utf-8")
            homepage = (site / "index.html").read_text(encoding="utf-8")
            companion = (site / "profile.html").read_text(encoding="utf-8")

        self.assertIn("- Name: Aoife O'Brien\n", llms)
        # & still follows the Markdown entity policy; only the quotes changed.
        self.assertIn('- Employer: Smith "Widgets" &amp; Sons\n', llms)
        self.assertIn("| Full name | Aoife O'Brien |", profile)
        for name, text in (("llms.txt", llms), ("profile.md", profile), ("llms-full.txt", full)):
            with self.subTest(name=name):
                self.assertNotIn("&#x27;", text)
                self.assertNotIn("&quot;", text)
        # HTML keeps attribute-safe escaping, in templates and in companions.
        self.assertIn('<meta name="author" content="Aoife O&#x27;Brien">', homepage)
        self.assertNotIn('content="Aoife O\'Brien', homepage)
        self.assertIn("Aoife O&#x27;Brien", companion)
        self.assertNotIn("Aoife O'Brien", companion)

    def test_fill_escapes_quotes_unless_the_target_is_markdown(self) -> None:
        cfg = {"FULL_NAME": self.NAME, "EMPLOYER": self.EMPLOYER, "EMAIL": "o'b@example.test"}
        self.assertEqual(fill("{{FULL_NAME}}", cfg), "Aoife O&#x27;Brien")
        self.assertEqual(fill("{{FULL_NAME}}", cfg, markdown=True), self.NAME)
        self.assertEqual(fill("{{EMPLOYER}}", cfg, markdown=True), 'Smith "Widgets" &amp; Sons')
        # The contact address keeps its own rules in both targets.
        self.assertEqual(fill("{{EMAIL}}", cfg, markdown=True), fill("{{EMAIL}}", cfg))


class ArticleDateMessageTests(unittest.TestCase):
    def article(self, root: Path, metadata: str) -> None:
        writing = root / "template" / "writing"
        writing.mkdir(parents=True, exist_ok=True)
        (root / "template" / "index.html").write_text("<h1>Home</h1>\n", encoding="utf-8")
        (writing / "notes.md").write_text(
            "<!--\ntitle: Notes\n%s\n-->\n# Notes\n\nBody.\n" % metadata, encoding="utf-8")

    def test_build_names_the_article_and_field_not_last_updated(self) -> None:
        cfg = config()
        for metadata, field in (("updated: 2026-13-01", "article updated date"),
                                ("published: 2026-02-30", "article published date")):
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.article(root, metadata)
                with self.assertRaises(ValueError) as raised:
                    build_site_staged(str(root / "template"), str(root / "site"), cfg)
                message = str(raised.exception)
                self.assertIn("writing/notes.md", message)
                self.assertIn(field + " must be a calendar-valid YYYY-MM-DD date", message)
                self.assertNotIn("LAST_UPDATED", message)
                report = review_articles(root / "template", cfg)
                self.assertEqual(report["articles"][0]["errors"],
                                 [field + " must be a calendar-valid YYYY-MM-DD date"])

    def test_config_date_is_still_reported_as_last_updated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.article(root, "desc: No article date")
            with self.assertRaisesRegex(ValueError, "LAST_UPDATED must be a calendar-valid"):
                build_site_staged(str(root / "template"), str(root / "site"),
                                  config(LAST_UPDATED="2026-13-01"))

    def test_article_command_names_the_option(self) -> None:
        for option in ("published", "updated"):
            with self.subTest(option=option), tempfile.TemporaryDirectory() as directory:
                (Path(directory) / "template").mkdir()
                with self.assertRaisesRegex(ValueError, "^--%s must be a calendar-valid" % option):
                    create_article(directory, "notes", "Notes", **{option: "2026-13-01"})


if __name__ == "__main__":
    unittest.main()
