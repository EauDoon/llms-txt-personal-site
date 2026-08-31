from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "eval" / "identity_questions.json"
SCRIPT = ROOT / "scripts" / "score_identity_eval.py"
sys.path.insert(0, str(ROOT / "scripts"))

from score_identity_eval import load_eval, score_answer


class IdentityEvalTests(unittest.TestCase):
    def test_eval_has_ten_generic_sourced_questions_and_no_stored_scores(self) -> None:
        dataset = load_eval(DATA)
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

        markers = (
            b"straits" + b"x",
            b"xsgd",
            b"xusd",
            b"daniel" + b"oon",
            b"eau" + b"doon",
        )
        compact = re.sub(rb"[\s_-]+", b"", DATA.read_bytes().lower())
        self.assertFalse(any(marker in compact for marker in markers))

        for question in questions:
            with self.subTest(question=question["id"]):
                self.assertRegex(question["id"], r"^[a-z][a-z0-9_]*$")
                self.assertTrue(question["question"].strip())
                self.assertTrue(question["gold_answer"].strip())
                self.assertTrue(question["must_include"])
                self.assertNotIn("score", question)
                self.assertNotIn("model", question)

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

    def test_score_requires_all_gold_phrases_and_rejects_known_contradictions(self) -> None:
        questions = {item["id"]: item for item in load_eval(DATA)["questions"]}

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
            item["id"]: item for item in load_eval(DATA)["questions"]
        }["current_title"]
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "current_title", "--data", str(DATA)],
            input=question["gold_answer"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["passed"])
        self.assertEqual(result["question_id"], "current_title")
        self.assertIn("mechanical phrase coverage", result["scoring_note"])

    @staticmethod
    def normalized(value: str) -> str:
        return " ".join(value.casefold().split())


if __name__ == "__main__":
    unittest.main()
