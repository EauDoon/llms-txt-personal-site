from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fork.py"


class ForkTests(unittest.TestCase):
    def load_module(self):
        self.assertTrue(SCRIPT.is_file(), "one-sitting fork command is missing")
        spec = importlib.util.spec_from_file_location("fork_under_test", SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def customized_config(self, module):
        sample = json.loads(
            (ROOT / "site.config.example.json").read_text(encoding="utf-8")
        )
        current = dict(sample)
        for key in module.CONFIG_KEYS_TO_REPLACE:
            if key == "KNOWS_ABOUT":
                current[key] = ["Verified work domain"]
            elif key == "ALUMNI_OF":
                current[key] = []
            else:
                current[key] = "signed-%s" % key.lower()
        current["FORK_FACTS_CONFIRMED"] = True
        current["FORK_ABSENCES_CONFIRMED"] = True
        return sample, current

    def test_init_copies_sample_config_once_without_overwriting(self) -> None:
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            sample = b'{"FULL_NAME": "Your Full Name"}\n'
            (repo / "site.config.example.json").write_bytes(sample)

            self.assertEqual(module.initialize(repo), 0)
            current = repo / "site.config.json"
            self.assertEqual(current.read_bytes(), sample)

            current.write_text('{"FULL_NAME": "Signed Name"}\n', encoding="utf-8")
            self.assertEqual(module.initialize(repo), 1)
            self.assertEqual(
                current.read_text(encoding="utf-8"),
                '{"FULL_NAME": "Signed Name"}\n',
            )

    def test_sample_fork_names_config_and_template_gaps(self) -> None:
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copy2(ROOT / "site.config.example.json", repo)
            shutil.copy2(
                ROOT / "site.config.example.json",
                repo / "site.config.json",
            )
            template = repo / "template"
            template.mkdir()
            (template / "profile.md").write_text(
                "# Profile\n\n- Area one\n",
                encoding="utf-8",
            )

            issues = module.readiness_issues(repo)

            self.assertTrue(
                any("FULL_NAME" in issue and "sample" in issue for issue in issues),
                issues,
            )
            self.assertTrue(
                any("FORK_FACTS_CONFIRMED" in issue for issue in issues),
                issues,
            )
            self.assertTrue(
                any("template/profile.md" in issue and "Area one" in issue for issue in issues),
                issues,
            )

    def test_ready_fork_runs_build_then_quality_in_one_command(self) -> None:
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            sample, current = self.customized_config(module)
            (repo / "site.config.example.json").write_text(
                json.dumps(sample),
                encoding="utf-8",
            )
            (repo / "site.config.json").write_text(
                json.dumps(current),
                encoding="utf-8",
            )
            (repo / "template").mkdir()
            scripts = repo / "scripts"
            scripts.mkdir()
            (scripts / "build.py").write_text("", encoding="utf-8")
            (scripts / "quality_check.py").write_text("", encoding="utf-8")

            commands = []

            def runner(command, **kwargs):
                commands.append((command, kwargs))
                return SimpleNamespace(returncode=0)

            self.assertEqual(module.run(repo, runner=runner), 0)
            self.assertEqual(
                [command for command, _ in commands],
                [
                    [sys.executable, str(scripts / "build.py")],
                    [sys.executable, str(scripts / "quality_check.py")],
                ],
            )
            self.assertTrue(all(item[1]["cwd"] == repo for item in commands))

    def test_partial_sample_collection_values_are_still_named(self) -> None:
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            sample, current = self.customized_config(module)
            current["KNOWS_ABOUT"] = [sample["KNOWS_ABOUT"][0], "Verified domain"]
            (repo / "site.config.example.json").write_text(
                json.dumps(sample),
                encoding="utf-8",
            )
            (repo / "site.config.json").write_text(
                json.dumps(current),
                encoding="utf-8",
            )
            (repo / "template").mkdir()

            issues = module.readiness_issues(repo)

            self.assertTrue(
                any(
                    "KNOWS_ABOUT" in issue
                    and sample["KNOWS_ABOUT"][0] in issue
                    for issue in issues
                ),
                issues,
            )

    def test_blank_required_identity_fact_is_named(self) -> None:
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            sample, current = self.customized_config(module)
            current["SUMMARY"] = "   "
            (repo / "site.config.example.json").write_text(
                json.dumps(sample),
                encoding="utf-8",
            )
            (repo / "site.config.json").write_text(
                json.dumps(current),
                encoding="utf-8",
            )
            (repo / "template").mkdir()

            issues = module.readiness_issues(repo)

            self.assertTrue(
                any("SUMMARY" in issue and "nonempty string" in issue for issue in issues),
                issues,
            )

    def test_non_object_config_is_named_instead_of_crashing(self) -> None:
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            sample, _ = self.customized_config(module)
            (repo / "site.config.example.json").write_text(
                json.dumps(sample),
                encoding="utf-8",
            )
            (repo / "site.config.json").write_text(
                "[]",
                encoding="utf-8",
            )

            self.assertEqual(
                module.readiness_issues(repo),
                ["site.config.example.json and site.config.json must contain JSON objects"],
            )

    def test_renamed_example_writing_still_reports_starter_prose(self) -> None:
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            sample, current = self.customized_config(module)
            (repo / "site.config.example.json").write_text(
                json.dumps(sample),
                encoding="utf-8",
            )
            (repo / "site.config.json").write_text(
                json.dumps(current),
                encoding="utf-8",
            )
            writing = repo / "template" / "writing"
            writing.mkdir(parents=True)
            (writing / "renamed.md").write_text(
                "# Example Depth Page: Replace This Title\n",
                encoding="utf-8",
            )

            issues = module.readiness_issues(repo)

            self.assertTrue(
                any(
                    "template/writing/renamed.md" in issue
                    and "Example Depth Page" in issue
                    for issue in issues
                ),
                issues,
            )

    def test_generated_index_link_does_not_require_editing_html(self) -> None:
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            sample, current = self.customized_config(module)
            (repo / "site.config.example.json").write_text(
                json.dumps(sample),
                encoding="utf-8",
            )
            (repo / "site.config.json").write_text(
                json.dumps(current),
                encoding="utf-8",
            )
            template = repo / "template"
            template.mkdir()
            shutil.copy2(ROOT / "template" / "index.html", template / "index.html")

            issues = module.readiness_issues(repo)

            self.assertFalse(
                any("template/index.html" in issue for issue in issues),
                issues,
            )

    def test_publishable_starters_make_no_category_query_claims(self) -> None:
        forbidden = (
            "who should i talk to about",
            "who can help with",
            "what they are a good first call about",
            "relevant queries:",
            "category questions",
            "domain you want to be found for",
            "category you want to be surfaced for",
        )
        paths = [ROOT / "site.config.example.json"]
        paths.extend(path for path in (ROOT / "template").rglob("*") if path.is_file())
        paths.extend(path for path in (ROOT / "example").rglob("*") if path.is_file())

        for path in paths:
            content = path.read_text(encoding="utf-8", errors="ignore").casefold()
            for phrase in forbidden:
                with self.subTest(path=path.relative_to(ROOT), phrase=phrase):
                    self.assertNotIn(phrase, content)

    def test_readme_exposes_the_one_sitting_commands(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("python scripts/fork.py --init", readme)
        self.assertIn("python scripts/fork.py", readme)
        self.assertNotIn("## Licence", readme)


if __name__ == "__main__":
    unittest.main()
