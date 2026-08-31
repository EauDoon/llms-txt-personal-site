#!/usr/bin/env python3
"""Score one pasted answer against the generic identity-question gold set."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "eval" / "identity_questions.json"
SCORING_NOTE = (
    "This is mechanical phrase coverage, not a live-model evaluation or proof "
    "that the answer contains no unsupported claims. Review the answer before publication."
)


def normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _string_list(value: object, field: str, question_id: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError("%s.%s must be a list of nonempty strings" % (question_id, field))
    return value


def load_eval(path: Path | str = DEFAULT_DATA) -> dict[str, object]:
    data_path = Path(path)
    try:
        dataset = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read identity eval data at %s: %s" % (data_path, exc)) from exc

    if not isinstance(dataset, dict) or not isinstance(dataset.get("questions"), list):
        raise ValueError("identity eval data must contain a questions list")
    if "scores" in dataset or "runs" in dataset:
        raise ValueError("identity eval data must not contain stored scores or runs")

    seen = set()
    for index, question in enumerate(dataset["questions"]):
        if not isinstance(question, dict):
            raise ValueError("questions[%d] must be an object" % index)
        question_id = question.get("id")
        if not isinstance(question_id, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*", question_id
        ):
            raise ValueError("questions[%d].id must be a lowercase identifier" % index)
        if question_id in seen:
            raise ValueError("duplicate identity question id: %s" % question_id)
        seen.add(question_id)

        for field in ("question", "gold_answer"):
            if not isinstance(question.get(field), str) or not question[field].strip():
                raise ValueError("%s.%s must be a nonempty string" % (question_id, field))
        _string_list(question.get("source_files"), "source_files", question_id)
        required = _string_list(question.get("must_include"), "must_include", question_id)
        if not required:
            raise ValueError("%s.must_include must not be empty" % question_id)
        _string_list(question.get("must_not_include", []), "must_not_include", question_id)
        patterns = _string_list(
            question.get("must_not_match", []), "must_not_match", question_id
        )
        for pattern in patterns:
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                raise ValueError(
                    "%s.must_not_match contains an invalid pattern: %s"
                    % (question_id, pattern)
                ) from exc

    return dataset


def score_answer(question: dict[str, object], answer: str) -> dict[str, object]:
    normalized_answer = normalize(answer)
    required = question["must_include"]
    missing = [
        phrase for phrase in required if normalize(phrase) not in normalized_answer
    ]
    contradictions = [
        phrase
        for phrase in question.get("must_not_include", [])
        if normalize(phrase) in normalized_answer
    ]
    contradictions.extend(
        pattern
        for pattern in question.get("must_not_match", [])
        if re.search(pattern, answer, re.IGNORECASE)
    )
    earned = len(required) - len(missing)
    possible = len(required)
    return {
        "passed": not missing and not contradictions,
        "earned": earned,
        "possible": possible,
        "missing": missing,
        "contradictions": contradictions,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score a pasted assistant answer against one generic identity question."
    )
    parser.add_argument("question_id", nargs="?", help="Question identifier to score")
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA,
        help="Identity eval JSON file",
    )
    parser.add_argument(
        "--list", action="store_true", help="List question identifiers and prompts"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        dataset = load_eval(args.data)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    questions = {question["id"]: question for question in dataset["questions"]}
    if args.list:
        for question in dataset["questions"]:
            print("%s\t%s" % (question["id"], question["question"]))
        return 0
    if not args.question_id:
        print("error: question_id is required unless --list is used", file=sys.stderr)
        return 2
    if args.question_id not in questions:
        print("error: unknown question_id: %s" % args.question_id, file=sys.stderr)
        return 2

    if sys.stdin.isatty():
        print("Paste the assistant answer, then send end-of-file:", file=sys.stderr)
    answer = sys.stdin.read()
    if not answer.strip():
        print("error: no assistant answer was provided on standard input", file=sys.stderr)
        return 2

    question = questions[args.question_id]
    result = {
        "question_id": question["id"],
        "question": question["question"],
        "gold_answer": question["gold_answer"],
        "source_files": question["source_files"],
        **score_answer(question, answer),
        "scoring_note": SCORING_NOTE,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
