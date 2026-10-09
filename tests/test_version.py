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

from http_client import fetch_url
from version import PROJECT, __version__

# SemVer 2.0.0, from semver.org.
SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)
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
