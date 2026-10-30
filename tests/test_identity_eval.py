from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "eval" / "identity_questions.json"
SCRIPT = ROOT / "scripts" / "score_identity_eval.py"
# CI runs the suite before site.config.json exists, and a developer may have
# a real one, so every run names the sample config explicitly.
EXAMPLE_CONFIG_PATH = ROOT / "site.config.example.json"
EXAMPLE_CONFIG = json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "scripts"))
# tests/ is not a package; make its helper importable however the suite runs.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from identity_markers import contains_marker
from score_identity_eval import has_tokens, load_eval, score_answer


def run_scorer(*args: str, answer: str = "", script: Path = SCRIPT, cwd: Path | None = None):
    return subprocess.run([sys.executable, str(script), *args], input=answer, capture_output=True,
                          text=True, encoding="utf-8", check=False, cwd=cwd)


class IdentityEvalTests(unittest.TestCase):
    def test_eval_has_ten_generic_sourced_questions_and_no_stored_scores(self) -> None:
        dataset = load_eval(DATA, EXAMPLE_CONFIG)
        questions = dataset["questions"]
        expected_ids = [
            "full_name",
            "current_title",
            "current_employer",
            "location",
            "contact_email",
            "linkedin",
            "x_profile",
            "current_role_location",
            "employment_dates",
            "podcast_absence",
        ]

        self.assertEqual([question["id"] for question in questions], expected_ids)
        self.assertNotIn("scores", dataset)
        self.assertNotIn("runs", dataset)

        self.assertFalse(contains_marker(DATA.read_bytes()))

        for question in questions:
            with self.subTest(question=question["id"]):
                self.assertRegex(question["id"], r"^[a-z][a-z0-9_]*$")
                self.assertTrue(question["question"].strip())
                self.assertTrue(question["gold_answer"].strip())
                self.assertTrue(question["must_include"])
                self.assertNotIn("score", question)
                self.assertNotIn("model", question)
                self.assertNotIn("{{", json.dumps(question))

                source_texts = []
                for source_name in question["source_files"]:
                    source = (ROOT / source_name).resolve()
                    self.assertTrue(source.is_relative_to((ROOT / "example").resolve()))
                    self.assertTrue(source.is_file(), source_name)
                    source_texts.append(source.read_text(encoding="utf-8"))

                gold = self.normalized(question["gold_answer"])
                self.assertTrue(
                    any(gold in self.normalized(source) for source in source_texts),
                    "gold answer is not copied from its named generic example source",
                )
                for required in question["must_include"]:
                    self.assertIn(self.normalized(required), gold)

    def test_shipped_answers_follow_the_config(self) -> None:
        # Every repeated fact is a token, so a fork's facts fill the eval.
        raw = {question["id"]: question for question in load_eval(DATA)["questions"]}
        for question_id, token in (("full_name", "{{FULL_NAME}}"), ("current_title", "{{JOB_TITLE}}"),
                                   ("current_employer", "{{EMPLOYER}}"), ("location", "{{CITY}}"),
                                   ("contact_email", "{{EMAIL}}"), ("linkedin", "{{LINKEDIN_SLUG}}"),
                                   ("x_profile", "{{X_HANDLE}}"), ("employment_dates", "{{ABSENCE_EMPLOYMENT_DATES}}"),
                                   ("podcast_absence", "{{ABSENCE_RECORDED_MEDIA}}"),
                                   ("podcast_absence", "{{LAST_UPDATED}}")):
            with self.subTest(question=question_id, token=token):
                self.assertIn(token, raw[question_id]["gold_answer"])
                self.assertTrue(has_tokens(raw[question_id]))
        self.assertIn("{{LAST_UPDATED}}", raw["podcast_absence"]["must_include"])
        self.assertEqual(raw["current_employer"]["must_not_include"], ["Previous Employer"])

    def test_gold_answers_pass_their_own_scorer(self) -> None:
        for question in load_eval(DATA, EXAMPLE_CONFIG)["questions"]:
            with self.subTest(question=question["id"]):
                result = score_answer(question, question["gold_answer"])

                self.assertEqual(
                    result["missing"],
                    [],
                    "the gold answer does not contain every required phrase",
                )
                self.assertEqual(
                    result["contradictions"],
                    [],
                    "the gold answer is rejected by its own contradiction list",
                )
                self.assertTrue(result["passed"])

    def test_score_requires_all_gold_phrases_and_rejects_known_contradictions(self) -> None:
        questions = {item["id"]: item for item in load_eval(DATA, EXAMPLE_CONFIG)["questions"]}

        correct = score_answer(
            questions["current_role_location"],
            questions["current_role_location"]["gold_answer"],
        )
        self.assertTrue(correct["passed"])
        self.assertEqual(correct["earned"], correct["possible"])
        self.assertEqual(correct["missing"], [])
        self.assertEqual(correct["contradictions"], [])

        incomplete = score_answer(
            questions["current_role_location"], "Your Employer"
        )
        self.assertFalse(incomplete["passed"])
        self.assertLess(incomplete["earned"], incomplete["possible"])
        self.assertTrue(incomplete["missing"])

        contradictory = score_answer(
            questions["current_title"],
            "Your Exact Job Title, also Previous title.",
        )
        self.assertFalse(contradictory["passed"])
        self.assertEqual(contradictory["missing"], [])
        self.assertEqual(contradictory["contradictions"], ["Previous title"])

    def test_cli_scores_an_answer_pasted_on_standard_input(self) -> None:
        question = {
            item["id"]: item for item in load_eval(DATA, EXAMPLE_CONFIG)["questions"]
        }["current_title"]
        completed = run_scorer("current_title", "--data", str(DATA), "--config", str(EXAMPLE_CONFIG_PATH),
                               answer=question["gold_answer"])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["passed"])
        self.assertEqual(result["question_id"], "current_title")
        self.assertIn("mechanical phrase coverage", result["scoring_note"])
        self.assertEqual(completed.stderr, "")

    def test_a_changed_fact_is_scored_from_the_config(self) -> None:
        # After the documented change-one-fact flow, the eval used to score
        # the correct new title as missing and demand the old date.
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "site.config.json"
            config.write_text(json.dumps(dict(EXAMPLE_CONFIG, JOB_TITLE="Synthetic Staff Engineer",
                                              LAST_UPDATED="2026-10-31")), encoding="utf-8")
            new = run_scorer("current_title", "--config", str(config), answer="Synthetic Staff Engineer")
            old = run_scorer("current_title", "--config", str(config), answer="Your Exact Job Title")
            dated = run_scorer("podcast_absence", "--config", str(config),
                               answer="No podcast, video interview or recorded AMA was located as of 2026-10-31.")
            stale = run_scorer("podcast_absence", "--config", str(config),
                               answer="No podcast, video interview or recorded AMA was located as of 2026-01-01.")
            listed = run_scorer("--list", "--config", str(config))
        self.assertEqual(new.returncode, 0, new.stdout + new.stderr)
        self.assertEqual(json.loads(new.stdout)["gold_answer"], "Synthetic Staff Engineer")
        self.assertEqual(old.returncode, 1)
        self.assertEqual(json.loads(old.stdout)["missing"], ["Synthetic Staff Engineer"])
        self.assertEqual(dated.returncode, 0, dated.stdout + dated.stderr)
        self.assertEqual(stale.returncode, 1)
        self.assertEqual(json.loads(stale.stdout)["missing"], ["2026-10-31"])
        self.assertEqual(listed.returncode, 0)
        self.assertEqual(new.stderr + listed.stderr, "")

    def custom_eval(self, directory: str, question: dict) -> Path:
        path = Path(directory) / "eval.json"
        base = {"id": "custom", "question": "Who?", "gold_answer": "Answer", "source_files": ["example/profile.md"],
                "must_include": ["Answer"]}
        path.write_text(json.dumps({"version": 1, "questions": [dict(base, **question)]}), encoding="utf-8")
        return path

    def test_a_token_without_a_config_value_stops_with_its_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(json.dumps(dict(EXAMPLE_CONFIG, EMPTY="  ")), encoding="utf-8")
            for key in ("NOT_A_KEY", "KNOWS_ABOUT", "EMPTY"):
                with self.subTest(key=key):
                    data = self.custom_eval(directory, {"gold_answer": "{{%s}}" % key, "must_include": ["{{%s}}" % key]})
                    result = run_scorer("custom", "--data", str(data), "--config", str(config), answer="x")
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("custom uses {{%s}}, but config.json has no nonempty string value for %s"
                                  % (key, key), result.stderr)
            data = self.custom_eval(directory, {"gold_answer": "{{FULL_NAME}}", "must_include": ["{{FULL_NAME}}"]})
            unreadable = run_scorer("custom", "--data", str(data), "--config", str(Path(directory) / "missing.json"),
                                    answer="x")
        self.assertEqual(unreadable.returncode, 2)
        self.assertIn("cannot read config at", unreadable.stderr)

    def test_an_eval_without_tokens_scores_exactly_as_before(self) -> None:
        # Every eval written for 1.0.0 has no tokens. It never reads a config,
        # so a missing or broken one changes nothing.
        with tempfile.TemporaryDirectory() as directory:
            data = self.custom_eval(directory, {})
            expected = {"question_id": "custom", "question": "Who?", "gold_answer": "Answer",
                        "source_files": ["example/profile.md"], "passed": True, "earned": 1, "possible": 1,
                        "missing": [], "contradictions": [],
                        "scoring_note": ("This is mechanical phrase coverage, not a live-model evaluation or proof "
                                         "that the answer contains no unsupported claims. Review the answer "
                                         "before publication.")}
            for extra in ((), ("--config", str(Path(directory) / "missing.json"))):
                with self.subTest(extra=extra):
                    result = run_scorer("custom", "--data", str(data), *extra, answer="The Answer.")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, json.dumps(expected, indent=2, ensure_ascii=False) + "\n")
                    self.assertEqual(result.stderr, "")
            self.assertEqual(load_eval(data), load_eval(data, EXAMPLE_CONFIG))

    def test_without_a_site_config_the_sample_config_fills_the_answers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "eval", repo / "eval")
            shutil.copyfile(EXAMPLE_CONFIG_PATH, repo / "site.config.example.json")
            script = repo / "scripts" / "score_identity_eval.py"
            fallback = run_scorer("current_title", answer="Your Exact Job Title", script=script, cwd=repo)
            (repo / "site.config.json").write_text(json.dumps(dict(EXAMPLE_CONFIG, JOB_TITLE="Fork Title")),
                                                   encoding="utf-8-sig")
            forked = run_scorer("current_title", answer="Fork Title", script=script, cwd=repo)
        self.assertEqual(fallback.returncode, 0, fallback.stdout + fallback.stderr)
        self.assertIn("note: site.config.json not found; answers are filled from site.config.example.json",
                      fallback.stderr)
        self.assertEqual(forked.returncode, 0, forked.stdout + forked.stderr)
        self.assertEqual(forked.stderr, "")

    def test_a_filled_gold_answer_that_fails_its_own_lists_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "site.config.json"
            config.write_text(json.dumps(dict(
                EXAMPLE_CONFIG, ABSENCE_EMPLOYMENT_DATES="No employment dates before 2019 are published here.")),
                encoding="utf-8")
            result = run_scorer("current_title", "--config", str(config), answer="Your Exact Job Title")
        # A warning, not an exit: the question being scored is unaffected.
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("warning: employment_dates: the filled gold answer fails its own lists", result.stderr)
        self.assertIn("adapt this question to your site", result.stderr)
        self.assertNotIn("current_title:", result.stderr)

    def test_list_prints_filled_questions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = self.custom_eval(directory, {"question": "Where does {{FULL_NAME}} work?",
                                                "gold_answer": "{{EMPLOYER}}", "must_include": ["{{EMPLOYER}}"]})
            result = run_scorer("--list", "--data", str(data), "--config", str(EXAMPLE_CONFIG_PATH))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["custom\tWhere does Your Full Name work?"])

    @staticmethod
    def normalized(value: str) -> str:
        return " ".join(value.casefold().split())


if __name__ == "__main__":
    unittest.main()
