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
from urllib.parse import unquote, urlsplit

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


# Content types a host sends by default, where template/_headers sets none.
DEFAULT_TYPES = {".html": "text/html; charset=utf-8", ".json": "application/json", ".js": "text/javascript",
                 ".xml": "application/xml", ".css": "text/css"}


def host_headers(path: str) -> dict[str, list[str]]:
    """Return the headers Cloudflare Pages sends for a path under template/_headers."""
    headers: dict[str, list[str]] = {}
    for pattern, rules in cloudflare_rules((TEMPLATE / "_headers").read_text(encoding="utf-8")):
        if pattern == "/*" or pattern == path or (pattern.startswith("/*.") and path.endswith(pattern[2:])):
            for name, value in rules:
                headers.setdefault(name, []).append(value)
    if "Content-Type" not in headers:
        suffix = ".html" if path == "/" else Path(path).suffix
        if suffix in DEFAULT_TYPES:
            headers["Content-Type"] = [DEFAULT_TYPES[suffix]]
    return headers


class LiveHeaderTests(unittest.TestCase):
    """Run the gate's --live section against canned responses.

    By default the canned host is a correct deployment: it serves this build's
    bytes at every published path, with the headers template/_headers sets.
    A test changes only the responses it is about.
    """

    def run_live_gate(self, home: dict[str, list[str]] | None = None, card: dict[str, list[str]] | None = None,
                      extra_config: dict | None = None, *, responses: dict | None = None,
                      exact: bool = False, prepare=None):
        config = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))
        config.update(extra_config or {})
        responses = responses or {}
        self.requests: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            with contextlib.redirect_stdout(io.StringIO()):
                build_site(str(TEMPLATE), str(site), dict(config, **json_block(config)))
            if prepare:
                prepare(site)
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
                parts = urlsplit(url)
                self.requests.append(url)
                # A real resolver fails on any other host, so a URL the gate
                # built wrongly must fail here too instead of being answered.
                if parts.scheme != "https" or parts.netloc != config["DOMAIN"]:
                    return 0, {}, b"", "getaddrinfo failed"
                path = parts.path
                local = site / "index.html" if path == "/" else site / unquote(path).lstrip("/")
                if path in responses:
                    status, headers, body = responses[path]
                    if body is None:
                        body = local.read_bytes()
                    return status, message(host_headers(path) if headers is None else headers), body, ""
                if path == "/.well-known/agent-card.json":
                    if card is None:
                        return 404, message({}), b"", ""
                    return 200, message(card), card_bytes, ""
                if not local.is_file() or local.name in {".htaccess", "_headers", "vercel.json"}:
                    return 404, message({}), b"", ""
                headers = home if path == "/" and home is not None else host_headers(path)
                return 200, message(headers), local.read_bytes(), ""

            agents: set[str | None] = set()
            output = io.StringIO()
            argv = ["quality_check.py", "--site", str(site), "--config", str(config_path),
                    "--live-exact" if exact else "--live"]
            with patch("http_client.fetch_url", fetch_url), patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as stopped:
                runpy.run_path(str(ROOT / "scripts" / "quality_check.py"), run_name="__main__")
            self.exit_code = stopped.exception.code
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

    def test_configured_ownership_proofs_are_requested_on_the_site(self) -> None:
        # The gate prefixed the site origin twice and requested
        # https://yourname.comhttps://yourname.com/google....html, so every
        # correct deployment with a verification token failed --live.
        home = {"X-Content-Type-Options": ["nosniff"], "Content-Security-Policy": ["default-src 'self'"]}
        verification = {"google_html_file": "google0123456789abcdef.html", "indexnow_key": "0123456789abcdef"}
        output = self.run_live_gate(home, None, {"verification": verification})
        self.assertIn("ok   https://yourname.com/google0123456789abcdef.html", output)
        self.assertIn("ok   https://yourname.com/0123456789abcdef.txt", output)
        self.assertNotIn("ownership proof missing", output)
        self.assertIn("FAILURES: 0", output)
        self.assertIn("https://yourname.com/google0123456789abcdef.html", self.requests)
        self.assertIn("https://yourname.com/0123456789abcdef.txt", self.requests)
        self.assertEqual({urlsplit(url).netloc for url in self.requests}, {"yourname.com"})

    def test_a_host_serving_this_build_passes_the_byte_check(self) -> None:
        output = self.run_live_gate()
        self.assertIn("ok   deployed manifest matches this build", output)
        self.assertRegex(output, r"ok   all \d+ published files are served with this build's bytes")
        self.assertIn("FAILURES: 0", output)
        self.assertIn("WARNINGS: 0", output)
        self.assertEqual(self.exit_code, 0)

    def test_a_stale_or_missing_deployed_file_warns_without_failing(self) -> None:
        responses = {"/profile.md": (200, None, b"# An older profile\n"),
                     "/search-index.json": (404, {}, b"")}
        output = self.run_live_gate(responses=responses)
        self.assertRegex(output, r"WARN 2 of \d+ published files are not served with this build's bytes: "
                                 r"/profile\.md \(bytes differ\), /search-index\.json \(404\)")
        self.assertIn("a host that rewrites responses (email obfuscation, minification, injected scripts", output)
        self.assertIn("FAILURES: 0", output)
        self.assertIn("WARNINGS: 1", output)
        self.assertEqual(self.exit_code, 0)

    def test_live_exact_fails_on_drift(self) -> None:
        responses = {"/profile.md": (200, None, b"# An older profile\n"),
                     "/search-index.json": (404, {}, b"")}
        output = self.run_live_gate(responses=responses, exact=True)
        self.assertRegex(output, r"FAIL 2 of \d+ published files are not served with this build's bytes")
        self.assertIn("FAILURES: 1", output)
        self.assertEqual(self.exit_code, 1)
        # A correct deployment still passes the exact check, and the header
        # warnings it reports are not escalated.
        output = self.run_live_gate({"X-Content-Type-Options": ["nosniff"]}, exact=True)
        self.assertIn("FAILURES: 0", output)
        self.assertIn("live homepage is served without Content-Security-Policy", output)
        self.assertEqual(self.exit_code, 0)

    def test_every_published_file_is_requested_once_at_its_served_path(self) -> None:
        self.run_live_gate()
        paths = [urlsplit(url).path for url in self.requests]
        self.assertEqual(len(paths), len(set(paths)), "a path was requested twice")
        for path in ("/", "/search.js", "/search-index.json", "/content-manifest.json", "/robots.txt",
                     "/404.html", "/feed.xml", "/writing/example-depth-page.md"):
            self.assertIn(path, paths)
        for path in ("/index.html", "/.htaccess", "/_headers", "/vercel.json"):
            self.assertNotIn(path, paths)

    def test_a_404_page_answered_as_an_error_is_not_drift(self) -> None:
        output = self.run_live_gate(responses={"/404.html": (404, {}, b"Not found")})
        self.assertIn("WARNINGS: 0", output)

    def test_a_differing_deployed_manifest_names_its_release(self) -> None:
        deployed = b'{"generator": "llms-txt-personal-site 0.9.0", "reviewed_date": "2025-12-01"}\n'
        output = self.run_live_gate(responses={"/content-manifest.json": (200, None, deployed)})
        self.assertIn("WARN deployed content-manifest.json differs from this build "
                      "(deployed generator llms-txt-personal-site 0.9.0, reviewed_date 2025-12-01)", output)
        # A body that is not the builder's manifest is not echoed.
        output = self.run_live_gate(responses={"/content-manifest.json": (200, None, b'{"generator": "<script>"}')})
        self.assertIn("WARN deployed content-manifest.json differs from this build\n", output)
        self.assertNotIn("<script>", output)
        output = self.run_live_gate(responses={"/content-manifest.json": (404, {}, b"")})
        self.assertIn("WARN deployed content-manifest.json is not served (404)", output)

    def test_a_build_without_a_manifest_warns_once(self) -> None:
        output = self.run_live_gate(prepare=lambda site: (site / "content-manifest.json").unlink())
        self.assertEqual(output.count("this build has no content-manifest.json"), 2, output)  # line and summary
        self.assertIn("WARNINGS: 1", output)
        self.assertNotIn("/content-manifest.json", [urlsplit(url).path for url in self.requests])

    def test_long_drift_lists_name_eight_paths_and_a_count(self) -> None:
        markdown = sorted(path.name for path in TEMPLATE.glob("*.md"))[:10]
        responses = {"/" + name: (404, {}, b"") for name in markdown}
        output = self.run_live_gate(responses=responses)
        self.assertIn(" and %d more" % (len(markdown) - 8), output)

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
