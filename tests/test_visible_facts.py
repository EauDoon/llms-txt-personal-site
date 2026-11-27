"""The homepage states every JSON-LD fact in visible text.

AI fetchers outside Google have been observed to drop JSON-LD and read only
the visible page, and Google requires FAQPage questions to be visible. These
tests build the sample site and compare the homepage's structured data with
its visible text.
"""
import contextlib
import html
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build import build_site, json_block  # noqa: E402


def built_home(config):
    with tempfile.TemporaryDirectory() as directory:
        site = Path(directory) / "site"
        with contextlib.redirect_stdout(io.StringIO()):
            build_site(str(ROOT / "template"), str(site), dict(config, **json_block(config)))
        return (site / "index.html").read_text(encoding="utf-8")


def visible_text(page):
    page = re.sub(r"<script\b.*?</script>", " ", page, flags=re.S)
    page = re.sub(r"<!--.*?-->", " ", page, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))


def graph(page):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    return [node for block in blocks for node in json.loads(block)["@graph"]]


class VisibleFactsTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))

    def test_every_faq_question_and_answer_is_visible(self):
        page = built_home(self.config)
        text = visible_text(page)
        faq = [node for node in graph(page) if node["@type"] == "FAQPage"][0]
        self.assertEqual(len(faq["mainEntity"]), 3)
        for question in faq["mainEntity"]:
            with self.subTest(question=question["name"]):
                self.assertIn(question["name"], text)
                self.assertIn(question["acceptedAnswer"]["text"], text)

    def test_person_and_employer_facts_are_visible(self):
        page = built_home(self.config)
        text = visible_text(page)
        nodes = {node["@type"]: node for node in graph(page)}
        person, employer = nodes["Person"], nodes["Organization"]
        expected = [person["jobTitle"], person["homeLocation"]["name"], employer["name"],
                    employer["description"]]
        expected += person["knowsAbout"]
        expected += [entry["name"] for entry in person["alumniOf"]]
        for value in expected:
            with self.subTest(value=value):
                self.assertIn(value, text)

    def test_facts_are_escaped_and_optional_fields_drop_out(self):
        config = dict(self.config, KNOWS_ABOUT=[], ALUMNI_OF=[], EMPLOYER_DESC="Builds <b>tools</b> & more.")
        page = built_home(config)
        self.assertIn("Builds &lt;b&gt;tools&lt;/b&gt; &amp; more.", page)
        self.assertNotIn("<dt>Knows about</dt>", page)
        self.assertNotIn("<dt>Previously</dt>", page)


if __name__ == "__main__":
    unittest.main()
