from __future__ import annotations

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

import regenerate_example


class RegenerateExampleTests(unittest.TestCase):
    def copy_repo(self, directory: str) -> Path:
        repo = Path(directory)
        shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "template", repo / "template")
        shutil.copytree(ROOT / "example", repo / "example")
        shutil.copy2(ROOT / "site.config.example.json", repo)
        return repo

    def run_script(self, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(repo / "scripts" / "regenerate_example.py"), *args],
                              cwd=repo, capture_output=True, text=True, check=False, timeout=120)

    def test_check_names_drift_and_a_plain_run_restores_byte_equality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.copy_repo(directory)
            example = repo / "example"
            clean = self.run_script(repo, "--check")
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)

            original = (example / "profile.md").read_bytes()
            (example / "profile.md").write_bytes(original + b"\nHand edit.\n")
            (example / "notes").mkdir()
            (example / "notes" / "stray.md").write_bytes(b"# Stray\n")

            stale = self.run_script(repo, "--check")
            self.assertEqual(stale.returncode, 1, stale.stdout + stale.stderr)
            self.assertIn("changed file: profile.md", stale.stdout)
            self.assertIn("missing generated file: notes/stray.md", stale.stdout)
            self.assertEqual((example / "profile.md").read_bytes(), original + b"\nHand edit.\n")

            repaired = self.run_script(repo)
            self.assertEqual(repaired.returncode, 0, repaired.stdout + repaired.stderr)
            self.assertIn("0 added, 1 changed, 1 removed", repaired.stdout)
            self.assertEqual((example / "profile.md").read_bytes(), original)
            self.assertFalse((example / "notes").exists())
            again = self.run_script(repo, "--check")
            self.assertEqual(again.returncode, 0, again.stdout + again.stderr)

    def test_missing_example_file_is_written_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.copy_repo(directory)
            expected = (repo / "example" / "writing" / "example-depth-page.html").read_bytes()
            shutil.rmtree(repo / "example" / "writing")
            stale = self.run_script(repo, "--check")
            self.assertEqual(stale.returncode, 1)
            self.assertIn("unexpected generated file: writing/example-depth-page.html", stale.stdout)
            repaired = self.run_script(repo)
            self.assertIn("2 added, 0 changed, 0 removed", repaired.stdout)
            self.assertEqual((repo / "example" / "writing" / "example-depth-page.html").read_bytes(), expected)

    def test_mirror_refuses_a_link_like_example_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated, example = root / "generated", root / "example"
            generated.mkdir()
            example.mkdir()
            (generated / "index.html").write_bytes(b"<h1>generated</h1>\n")

            def isjunction(path) -> bool:
                return os.path.normpath(str(path)) == os.path.normpath(str(example))

            with patch("build.os.path.isjunction", side_effect=isjunction, create=True):
                with self.assertRaisesRegex(ValueError, "link-like"):
                    regenerate_example.mirror(generated, example)
            self.assertEqual(list(example.iterdir()), [])

    def test_regenerator_reads_only_the_sample_config(self) -> None:
        source = (ROOT / "scripts" / "regenerate_example.py").read_text(encoding="utf-8")
        self.assertNotIn("--config", source)
        self.assertNotIn("site.config.json", source.replace("site.config.example.json", ""))
        self.assertEqual(regenerate_example.SAMPLE_CONFIG, ROOT / "site.config.example.json")


if __name__ == "__main__":
    unittest.main()
