"""The release version is written once and every surface reports the same one."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import version
from http_client import fetch_url
from version import PROJECT, __version__

SEMVER = version.SEMVER
CLIS = (
    "build.py",
    "quality_check.py",
    "check_artifacts.py",
    "verify_build.py",
    "review_build.py",
    "fork.py",
    "article.py",
    "score_identity_eval.py",
    "regenerate_example.py",
    "version.py",
)


class AgentRecorder(BaseHTTPRequestHandler):
    agents: list[str] = []

    def do_GET(self) -> None:
        AgentRecorder.agents.append(self.headers.get("User-Agent", ""))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args) -> None:
        pass


class VersionTests(unittest.TestCase):
    def test_version_is_semver(self) -> None:
        self.assertRegex(__version__, r"\A%s\Z" % SEMVER.pattern)
        self.assertEqual(PROJECT, "llms-txt-personal-site")

    def test_every_cli_reports_the_version_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            before = sorted(path.relative_to(repo) for path in repo.rglob("*") if "__pycache__" not in path.parts)
            for script in CLIS:
                with self.subTest(script=script):
                    result = subprocess.run([sys.executable, str(repo / "scripts" / script), "--version"],
                                            cwd=repo, capture_output=True, text=True, check=False, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(result.stdout.strip(), "%s %s" % (script, __version__))
            after = sorted(path.relative_to(repo) for path in repo.rglob("*") if "__pycache__" not in path.parts)
            self.assertEqual(after, before)

    def test_version_script_prints_the_bare_version(self) -> None:
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "version.py")],
                                capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, __version__ + "\n")

    def test_example_manifest_names_the_generating_release(self) -> None:
        manifest = json.loads((ROOT / "example" / "content-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], 1, "the manifest format version is independent")
        self.assertEqual(manifest["generator"], "%s %s" % (PROJECT, __version__),
                         "run python scripts/regenerate_example.py after changing the version")

    def test_http_client_sends_the_user_agent_it_is_given(self) -> None:
        AgentRecorder.agents = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), AgentRecorder)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            url = "http://127.0.0.1:%d/" % server.server_port
            status, _, body, error = fetch_url(url, timeout=5, user_agent="%s-quality-check/%s" % (PROJECT, __version__))
            fetch_url(url, timeout=5)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual((status, body, error), (200, b"ok", ""))
        self.assertEqual(AgentRecorder.agents,
                         ["%s-quality-check/%s" % (PROJECT, __version__), "llms-txt-personal-site-quality-check"])

    def test_changelog_structure_matches_the_version(self) -> None:
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Changelog\n"))
        self.assertIn("Keep a Changelog 1.1.0", text)
        self.assertIn("Semantic Versioning 2.0.0", text)
        found = version.sections(text)
        self.assertEqual(found[0][:2], ("Unreleased", None), "[Unreleased] must be the first section")
        released = found[1:]
        keys = []
        for name, stamp, body in released:
            with self.subTest(release=name):
                keys.append(version.parse_semver(name))
                self.assertTrue(version.valid_date(stamp), "released sections need a real YYYY-MM-DD date")
                self.assertTrue(body.strip(), "released sections need notes")
        self.assertEqual(keys, sorted(keys, reverse=True), "releases must be listed newest first")
        self.assertEqual(len(set(keys)), len(keys), "a release is listed twice")
        names = [name for name, _, _ in found]
        for name in names:
            with self.subTest(link=name):
                self.assertRegex(text, r"(?m)^\[%s\]: https://\S+$" % re.escape(name))
        if version.is_prerelease(__version__):
            self.assertNotIn(__version__, names, "a pre-release needs only [Unreleased]")
        else:
            self.assertIn(__version__, names, "a final version needs its own dated section")
            self.assertEqual(released[0][0], __version__, "the current version must be the newest release")

    def test_check_tag_and_notes_against_a_temporary_changelog(self) -> None:
        changelog = ("# Changelog\n\n## [Unreleased]\n\n## [2.1.0] - 2026-03-04\n\n### Fixed\n\n- A fix.\n\n"
                     "## [2.0.0] - 2026-02-30\n\n- Bad date.\n\n## [1.9.0]\n\n- Undated.\n\n"
                     "[Unreleased]: https://example.test/compare/v2.1.0...HEAD\n"
                     "[2.1.0]: https://example.test/releases/tag/v2.1.0\n")
        self.assertEqual(version.tag_problems("v2.1.0", "2.1.0", changelog), [])
        self.assertEqual(version.release_notes(changelog, "2.1.0"), "### Fixed\n\n- A fix.\n")
        cases = {
            ("v2.1.1", "2.1.0"): "does not match version",
            ("2.1.0", "2.1.0"): "does not match version",
            ("v2.2.0-rc.1", "2.2.0-rc.1"): "is a pre-release",
            ("v2.0.0", "2.0.0"): "no valid YYYY-MM-DD date",
            ("v1.9.0", "1.9.0"): "no valid YYYY-MM-DD date",
            ("v3.0.0", "3.0.0"): "has no [3.0.0] section",
        }
        for (tag, value), expected in cases.items():
            with self.subTest(tag=tag, version=value):
                problems = version.tag_problems(tag, value, changelog)
                self.assertTrue(any(expected in problem for problem in problems), problems)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CHANGELOG.md"
            path.write_text(changelog, encoding="utf-8")
            script = str(ROOT / "scripts" / "version.py")
            notes = subprocess.run([sys.executable, script, "--changelog", str(path), "--notes", "2.1.0"],
                                   capture_output=True, check=False, timeout=60)
            self.assertEqual(notes.returncode, 0, notes.stderr)
            self.assertEqual(notes.stdout, b"### Fixed\n\n- A fix.\n")
            missing = subprocess.run([sys.executable, script, "--changelog", str(path), "--notes", "9.9.9"],
                                     capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(missing.returncode, 1)
            self.assertIn("no [9.9.9] section", missing.stderr)
            tagged = subprocess.run([sys.executable, script, "--changelog", str(path), "--check-tag", "v" + __version__],
                                    capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(tagged.returncode, 1, "the temporary changelog has no section for the current version")

    def test_check_tag_on_this_tree(self) -> None:
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "version.py"), "--check-tag", "v" + __version__],
                                capture_output=True, text=True, check=False, timeout=60)
        if version.is_prerelease(__version__):
            self.assertEqual(result.returncode, 1)
            self.assertIn("is a pre-release", result.stderr)
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
            notes = subprocess.run([sys.executable, str(ROOT / "scripts" / "version.py"), "--notes", __version__],
                                   capture_output=True, check=False, timeout=60)
            self.assertEqual(notes.returncode, 0, notes.stderr)
            self.assertIn(b"### ", notes.stdout)

    def test_semver_ordering_follows_the_specification(self) -> None:
        ordered = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
                   "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1", "1.1.0", "2.0.0", "10.0.0"]
        self.assertEqual(sorted(ordered, key=version.parse_semver), ordered)
        for invalid in ("1.0", "01.0.0", "v1.0.0", "1.0.0-", ""):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                version.parse_semver(invalid)

    def test_http_client_loads_without_sibling_modules(self) -> None:
        # tests/test_http_client.py loads the client by file path with no
        # scripts/ on sys.path, so it must not import a sibling module.
        code = ("import importlib.util, sys; sys.path = [p for p in sys.path if 'scripts' not in p]; "
                "spec = importlib.util.spec_from_file_location('client', sys.argv[1]); "
                "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
                "print(module.fetch_url.__defaults__)")
        result = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT / "scripts" / "http_client.py")],
                                capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
