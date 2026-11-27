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
from build import build_site_staged
from publishing import review_articles


def config(**changes):
    cfg = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))
    cfg.update(changes)
    return cfg


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
