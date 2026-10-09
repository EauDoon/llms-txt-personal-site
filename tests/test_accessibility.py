"""Landmarks, skip links, link styling and page language in generated HTML.

The offline audit and the gate also read bare fragments in their own tests,
so these rules are enforced here, over the checked-in example and a fresh
build, rather than inside check_artifacts.audit.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "example"
sys.path.insert(0, str(ROOT / "scripts"))

from build import build_site, json_block, load_config


class Landmarks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.mains = 0
        self.ids: set[str] = set()
        self.skip_targets: list[str] = []
        self.styles: list[str] = []
        self._style: list[str] | None = None

    def handle_starttag(self, tag, attrs) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "html":
            self.lang = values.get("lang")
        elif tag == "main":
            self.mains += 1
        elif tag == "a" and "skip" in values.get("class", "") and values.get("href", "").startswith("#"):
            self.skip_targets.append(values["href"][1:])
        elif tag == "style":
            self._style = []

    def handle_data(self, data) -> None:
        if self._style is not None:
            self._style.append(data)

    def handle_endtag(self, tag) -> None:
        if tag == "style" and self._style is not None:
            self.styles.append("".join(self._style))
            self._style = None


def parse(path: Path) -> Landmarks:
    document = Landmarks()
    document.feed(path.read_text(encoding="utf-8"))
    document.close()
    return document


def link_rules(css: str) -> list[str]:
    """Return the declaration blocks of rules whose selector styles every link."""
    rules = []
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        names = [name.strip() for name in selectors.split(",")]
        if any(re.fullmatch(r"a(:[a-z-]+)?", name) for name in names):
            rules.append(body)
    return rules


class AccessibilityTests(unittest.TestCase):
    def html_pages(self) -> list[Path]:
        pages = sorted(EXAMPLE.rglob("*.html"))
        self.assertGreater(len(pages), 10)
        return pages

    def test_every_page_has_one_main_landmark_and_a_working_skip_link(self) -> None:
        for path in self.html_pages():
            with self.subTest(page=path.relative_to(EXAMPLE).as_posix()):
                document = parse(path)
                self.assertEqual(document.mains, 1)
                self.assertTrue(document.skip_targets, "no skip link")
                for target in document.skip_targets:
                    self.assertIn(target, document.ids)

    def test_links_are_never_told_apart_by_color_alone(self) -> None:
        # The accent color is under 3:1 against body text in both themes, so
        # links in prose need an underline (WCAG 1.4.1).
        for path in self.html_pages():
            with self.subTest(page=path.relative_to(EXAMPLE).as_posix()):
                for body in link_rules("\n".join(parse(path).styles)):
                    self.assertNotRegex(body, r"text-decoration\s*:\s*none")
        for name in ("index.html", "404.html", "writing/example-depth-page.html"):
            with self.subTest(explicit=name):
                rules = link_rules("\n".join(parse(EXAMPLE / name).styles))
                self.assertTrue(any(re.search(r"text-decoration\s*:\s*underline", body) for body in rules))

    def test_configured_language_reaches_every_page_and_article_metadata(self) -> None:
        config = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))
        config["SITE_LANGUAGE"] = "de"
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "site"
            with patch("sys.stdout"):
                build_site(str(ROOT / "template"), str(site), dict(config, **json_block(config)))
            pages = sorted(site.rglob("*.html"))
            self.assertGreater(len(pages), 10)
            for path in pages:
                with self.subTest(page=path.relative_to(site).as_posix()):
                    self.assertEqual(parse(path).lang, "de")
            article = (site / "writing" / "example-depth-page.html").read_text(encoding="utf-8")
            self.assertIn('"inLanguage": "de"', article)

    def test_example_pages_default_to_english(self) -> None:
        for path in self.html_pages():
            with self.subTest(page=path.relative_to(EXAMPLE).as_posix()):
                self.assertEqual(parse(path).lang, "en")

    def test_load_config_rejects_a_malformed_language_tag(self) -> None:
        config = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "site.config.json"
            for value in ("english!", "e", "en_US", "", 7):
                with self.subTest(value=value):
                    path.write_text(json.dumps(dict(config, SITE_LANGUAGE=value)), encoding="utf-8")
                    with patch("build.CONFIG", str(path)):
                        with self.assertRaisesRegex(SystemExit, "SITE_LANGUAGE"):
                            load_config()
            for value in ("de", "pt-BR", "zh-Hant-TW"):
                with self.subTest(value=value):
                    path.write_text(json.dumps(dict(config, SITE_LANGUAGE=value)), encoding="utf-8")
                    with patch("build.CONFIG", str(path)):
                        self.assertEqual(load_config()["SITE_LANGUAGE"], value)


if __name__ == "__main__":
    unittest.main()
