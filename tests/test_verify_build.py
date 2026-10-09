from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_build


class VerifyBuildTests(unittest.TestCase):
    def test_sample_config_verifies_without_touching_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "template", repo / "template")
            shutil.copyfile(ROOT / "site.config.example.json", repo / "site.config.json")
            result = subprocess.run([sys.executable, str(repo / "scripts" / "verify_build.py")], cwd=repo,
                                    capture_output=True, text=True, check=False, timeout=300)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Verified two reproducible builds and both offline artifact audits.", result.stdout)
            self.assertFalse((repo / "site").exists())

    def test_help_exits_before_reading_config_or_building(self) -> None:
        output = io.StringIO()
        with patch.object(verify_build, "load_config", side_effect=AssertionError("read config")), \
                patch.object(verify_build, "verify", side_effect=AssertionError("built")), \
                contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            verify_build.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("usage:", output.getvalue())

    def test_link_like_template_fails_with_one_clean_line(self) -> None:
        config = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "template"
            template.mkdir()
            (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")

            def isjunction(path) -> bool:
                return os.path.normpath(str(path)) == os.path.normpath(str(template))

            output = io.StringIO()
            with patch.object(verify_build, "TEMPLATE", str(template)), \
                    patch.object(verify_build, "load_config", return_value=config), \
                    patch("build.os.path.isjunction", side_effect=isjunction, create=True), \
                    contextlib.redirect_stdout(output):
                code = verify_build.main([])
        self.assertEqual(code, 1)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("FAIL "), lines)
        self.assertIn("link-like template root", lines[0])


if __name__ == "__main__":
    unittest.main()
