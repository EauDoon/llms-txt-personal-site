from __future__ import annotations

import contextlib
import io
import json
import re
import runpy
import sys
import tempfile
import unittest
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
sys.path.insert(0, str(ROOT / "scripts"))

from build import build_site, json_block
from version import PROJECT, __version__

# Headers every response gets from each host config, with identical values.
CONTRACT = (
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Content-Security-Policy",
    "X-Frame-Options",
    "Permissions-Policy",
    "Link",
)


def cloudflare_rules(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    rules: list[tuple[str, list[tuple[str, str]]]] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            rules.append((line.strip(), []))
        else:
            name, _, value = line.strip().partition(":")
            rules[-1][1].append((name.strip(), value.strip()))
    return rules


def vercel_rules(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    return [(rule["source"], [(header["key"], header["value"]) for header in rule["headers"]])
            for rule in json.loads(text)["headers"]]


def apache_global_headers(text: str) -> list[tuple[str, str]]:
    """Return `Header always set` directives outside any <Files> section."""
    depth, found = 0, []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"<Files(Match)?\b", stripped):
            depth += 1
        elif re.match(r"</Files(Match)?>", stripped):
            depth -= 1
        elif depth == 0:
            match = re.fullmatch(r'Header\s+always\s+set\s+(\S+)\s+"(.*)"', stripped)
            if match:
                found.append((match.group(1), match.group(2)))
    return found


def contract(headers: list[tuple[str, str]]) -> dict[str, str]:
    return {name: value for name, value in headers if name in CONTRACT}


class CspFit(HTMLParser):
    """Collect anything in a page that the shipped CSP would block."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.problems: list[str] = []
        self._inline_script = False

    @staticmethod
    def same_origin(url: str) -> bool:
        parts = urlsplit(url)
        return not parts.scheme and not parts.netloc

    def handle_starttag(self, tag, attrs) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        self.problems.extend("event handler %s on <%s>" % (key, tag) for key in values if key.startswith("on"))
        if tag == "script":
            media = values.get("type", "").split(";", 1)[0].strip().lower()
            if media == "application/ld+json":
                return
            if not values.get("src"):
                self._inline_script = True
                self.problems.append("inline executable <script>")
            elif not self.same_origin(values["src"]):
                self.problems.append("third-party script %s" % values["src"])
        elif tag == "img":
            src = values.get("src", "")
            if not (self.same_origin(src) or src.startswith("https:") or src.startswith("data:image/")):
                self.problems.append("image source %s" % src)
        elif tag == "link" and "stylesheet" in values.get("rel", "").lower().split():
            if not self.same_origin(values.get("href", "")):
                self.problems.append("third-party stylesheet %s" % values.get("href"))
        elif tag in {"iframe", "object", "embed", "base"}:
            self.problems.append("<%s> element" % tag)
        elif tag == "form" and values.get("action") and not self.same_origin(values["action"]):
            self.problems.append("form posts to %s" % values["action"])


class HostingConfigTests(unittest.TestCase):
    def read(self, name: str) -> str:
        return (TEMPLATE / name).read_text(encoding="utf-8")

    def test_vercel_serves_html_at_its_own_path(self) -> None:
        config = json.loads(self.read("vercel.json"))
        self.assertIn("cleanUrls", config, "keep the cleanUrls decision explicit")
        self.assertIsNot(
            config["cleanUrls"],
            True,
            "cleanUrls makes Vercel 308-redirect every .html URL to an extensionless "
            "path, but canonicals (quality_check.py head metadata), sitemap.xml, the "
            "feed and the --live check, which follows no redirects, all publish "
            "and request the .html path",
        )
        self.assertIsNot(config.get("trailingSlash"), True,
                         "a trailing-slash redirect would also move every published URL")

    def test_every_host_sends_the_same_security_and_discovery_headers(self) -> None:
        cloudflare = dict(cloudflare_rules(self.read("_headers")))["/*"]
        vercel = dict(vercel_rules(self.read("vercel.json")))["/(.*)"]
        apache = apache_global_headers(self.read(".htaccess"))
        expected = contract(cloudflare)
        self.assertEqual(sorted(expected), sorted(CONTRACT))
        self.assertEqual(contract(vercel), expected)
        self.assertEqual(contract(apache), expected)
        self.assertEqual(expected["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", expected["Content-Security-Policy"])
        self.assertIn("object-src 'none'", expected["Content-Security-Policy"])

    def test_no_header_is_set_by_both_a_specific_rule_and_the_catch_all(self) -> None:
        # Cloudflare Pages joins a header set by two matching rules with a
        # comma, which turned the Agent Card's CORS header into "*, *".
        for name, rules, catch_all in (("_headers", cloudflare_rules(self.read("_headers")), "/*"),
                                       ("vercel.json", vercel_rules(self.read("vercel.json")), "/(.*)")):
            everywhere = {header.lower() for header, _ in dict(rules)[catch_all]}
            for source, headers in rules:
                if source == catch_all:
                    continue
                with self.subTest(file=name, rule=source):
                    self.assertEqual(everywhere & {header.lower() for header, _ in headers}, set())

    def test_generated_pages_fit_the_shipped_csp(self) -> None:
        config = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "site"
            with contextlib.redirect_stdout(io.StringIO()):
                build_site(str(TEMPLATE), str(site), dict(config, **json_block(config)))
            pages = sorted(site.rglob("*.html"))
            self.assertGreater(len(pages), 10)
            for path in pages:
                with self.subTest(page=path.relative_to(site).as_posix()):
                    checker = CspFit()
                    checker.feed(path.read_text(encoding="utf-8"))
                    checker.close()
                    self.assertEqual(checker.problems, [])
            script = (site / "search.js").read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\beval\s*\(|new\s+Function\s*\(|setTimeout\s*\(\s*['\"]", script))
            self.assertIn("fetch(", script)


class LiveHeaderTests(unittest.TestCase):
    """Run the gate's --live section against canned responses."""

    def run_live_gate(self, home: dict[str, list[str]], card: dict[str, list[str]] | None):
        config = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            with contextlib.redirect_stdout(io.StringIO()):
                build_site(str(TEMPLATE), str(site), dict(config, **json_block(config)))
            card_bytes = b'{"name": "canned"}\n'
            if card is not None:
                (site / ".well-known").mkdir()
                (site / ".well-known" / "agent-card.json").write_bytes(card_bytes)
            config_path = root / "site.config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            def message(headers: dict[str, list[str]]) -> Message:
                result = Message()
                for name, values in headers.items():
                    for value in values:
                        result[name] = value
                return result

            def fetch_url(url, timeout=20, user_agent=None):
                agents.add(user_agent)
                path = urlsplit(url).path
                if path == "/":
                    return 200, message(home), b"", ""
                if path == "/.well-known/agent-card.json":
                    if card is None:
                        return 404, message({}), b"", ""
                    return 200, message(card), card_bytes, ""
                return 200, message({"Content-Type": ["text/markdown; charset=utf-8"],
                                     "Content-Disposition": ["inline"]}), b"", ""

            agents: set[str | None] = set()
            output = io.StringIO()
            argv = ["quality_check.py", "--site", str(site), "--config", str(config_path), "--live"]
            with patch("http_client.fetch_url", fetch_url), patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                runpy.run_path(str(ROOT / "scripts" / "quality_check.py"), run_name="__main__")
            # Every live request names the template release that made it.
            self.assertEqual(agents, {"%s-quality-check/%s" % (PROJECT, __version__)})
            return output.getvalue()

    def card_headers(self, *origins: str) -> dict[str, list[str]]:
        headers = {"Content-Type": ["application/a2a+json; charset=utf-8"],
                   "Cache-Control": ["public, max-age=3600"], "ETag": ['"1"']}
        if origins:
            headers["Access-Control-Allow-Origin"] = list(origins)
        return headers

    def test_missing_security_headers_warn_without_failing(self) -> None:
        output = self.run_live_gate({}, None)
        self.assertIn("WARN homepage sends X-Content-Type-Options: nosniff", output)
        self.assertIn("WARN homepage sends Content-Security-Policy", output)
        self.assertIn("live homepage is served without Content-Security-Policy", output)
        self.assertIn("FAILURES: 0", output)

        output = self.run_live_gate({"X-Content-Type-Options": ["nosniff"],
                                     "Content-Security-Policy": ["default-src 'self'"]}, None)
        self.assertIn("ok   homepage sends Content-Security-Policy", output)
        self.assertIn("WARNINGS: 0", output)

    def test_agent_card_cors_header_must_be_exactly_one_wildcard(self) -> None:
        home = {"X-Content-Type-Options": ["nosniff"], "Content-Security-Policy": ["default-src 'self'"]}
        for origins, passes in ((("*",), True), (("*, *",), False), (("*", "*"), False), ((), False),
                                (("https://example.test",), False)):
            with self.subTest(origins=origins):
                output = self.run_live_gate(home, self.card_headers(*origins))
                if passes:
                    self.assertIn("ok   A2A Agent Card sends Access-Control-Allow-Origin: *", output)
                    self.assertNotIn("Access-Control-Allow-Origin is not exactly *", output)
                else:
                    self.assertIn("FAIL A2A Agent Card sends Access-Control-Allow-Origin: *", output)
                    self.assertIn("live Agent Card Access-Control-Allow-Origin is not exactly *", output)


if __name__ == "__main__":
    unittest.main()
