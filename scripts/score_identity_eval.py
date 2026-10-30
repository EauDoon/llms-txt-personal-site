#!/usr/bin/env python3
"""Score one pasted answer against the generic identity-question gold set.

The question, gold answer, must_include and must_not_include fields may hold
{{KEY}} tokens, the placeholders the builder fills. Each is filled from the
site config, so the eval scores this site's current facts and follows a
changed title or date without a hand edit. must_not_match is a literal
regular expression. An eval without tokens never reads the config.
"""

from __future__ import annotations

import argparse
import json
import locale
import re
import sys
from pathlib import Path

from console_output import configure, dump_json
from version import __version__

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "eval" / "identity_questions.json"
DEFAULT_CONFIG = ROOT / "site.config.json"
EXAMPLE_CONFIG = ROOT / "site.config.example.json"
# The builder's placeholder syntax, so one spelling fills pages and the eval.
TOKEN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
FILLED_FIELDS = ("question", "gold_answer", "must_include", "must_not_include")
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


def has_tokens(question: dict[str, object]) -> bool:
    """Return whether any field the config fills holds a {{KEY}} token."""
    for field in FILLED_FIELDS:
        value = question.get(field, [])
        for text in (value if isinstance(value, list) else [value]):
            if isinstance(text, str) and TOKEN.search(text):
                return True
    return False


def fill_question(question: dict[str, object], config: dict[str, object],
                  config_name: str = "the config") -> dict[str, object]:
    """Return a copy of question with every {{KEY}} replaced by its config value.

    A key the config does not set to a nonempty string is an error. Scoring
    the literal token would report a correct answer as missing it.
    """
    def value(match: re.Match[str]) -> str:
        key = match.group(1)
        found = config.get(key)
        if not isinstance(found, str) or not found.strip():
            raise ValueError("%s uses {{%s}}, but %s has no nonempty string value for %s"
                             % (question["id"], key, config_name, key))
        return found

    filled = dict(question)
    for field in FILLED_FIELDS:
        if isinstance(filled.get(field), str):
            filled[field] = TOKEN.sub(value, filled[field])
        elif isinstance(filled.get(field), list):
            filled[field] = [TOKEN.sub(value, item) for item in filled[field]]
    return filled


def fill_eval(dataset: dict[str, object], config: dict[str, object],
              config_name: str = "the config") -> dict[str, object]:
    """Return the dataset with each question's tokens filled from config."""
    return dict(dataset, questions=[fill_question(question, config, config_name)
                                    for question in dataset["questions"]])


def self_check(dataset: dict[str, object], questions_with_tokens: set[str]) -> list[str]:
    """Name each filled question whose gold answer fails its own phrase lists.

    A fork that rewrote an absence sentence, or wrote a year into one, keeps
    the sample's literal fragments and patterns until it adapts the eval.
    """
    problems = []
    for question in dataset["questions"]:
        if question["id"] not in questions_with_tokens:
            continue
        result = score_answer(question, question["gold_answer"])
        if not result["passed"]:
            problems.append("%s: the filled gold answer fails its own lists (missing %s, contradictions %s); "
                            "adapt this question to your site"
                            % (question["id"], result["missing"], result["contradictions"]))
    return problems


def read_config(path: Path | str) -> dict[str, object]:
    """Return a site config as build.py reads it, a byte order mark allowed."""
    config_path = Path(path)
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read config at %s: %s" % (config_path, exc)) from exc
    if not isinstance(config, dict):
        raise ValueError("config at %s must contain a JSON object" % config_path)
    return config


def load_eval(path: Path | str = DEFAULT_DATA, config: dict[str, object] | None = None) -> dict[str, object]:
    """Read and validate an eval file, filling its tokens when config is given."""
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

    return dataset if config is None else fill_eval(dataset, config)


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


def read_answer(stream) -> str:
    """Return the answer on standard input, reading redirected bytes as UTF-8 first.

    Windows decodes redirected input in the ANSI code page, such as cp1252, so
    a UTF-8 answer was read as mojibake and a correct answer failed. Bytes
    that are not UTF-8 are still decoded in the stream's own encoding, as
    before, and only input that is neither is refused.
    """
    if stream.isatty():
        print("Paste the assistant answer, then send end-of-file:", file=sys.stderr)
        return stream.read()
    raw = getattr(stream, "buffer", None)
    if raw is None:
        return stream.read()
    data = raw.read()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        fallback = getattr(stream, "encoding", None) or locale.getpreferredencoding(False)
        try:
            text = data.decode(fallback)
        except (UnicodeDecodeError, LookupError):
            raise ValueError("standard input is not text in UTF-8 or %s" % fallback) from None
    # Text-mode reads translate line endings; keep doing so.
    return text.replace("\r\n", "\n").replace("\r", "\n")


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
        "--config",
        type=Path,
        help="Site config whose values fill {{KEY}} tokens in the eval (default: site.config.json, "
        "or site.config.example.json when that is missing); read only when the eval holds tokens",
    )
    parser.add_argument(
        "--list", action="store_true", help="List question identifiers and prompts, filled from the config"
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure()
    args = parse_args(argv)
    try:
        dataset = load_eval(args.data)
        with_tokens = {question["id"] for question in dataset["questions"] if has_tokens(question)}
        if with_tokens:
            config_path = args.config
            if config_path is None:
                config_path = DEFAULT_CONFIG
                if not config_path.is_file():
                    config_path = EXAMPLE_CONFIG
                    print("note: site.config.json not found; answers are filled from site.config.example.json",
                          file=sys.stderr)
            dataset = fill_eval(dataset, read_config(config_path), config_path.name)
            for problem in self_check(dataset, with_tokens):
                print("warning: %s" % problem, file=sys.stderr)
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

    try:
        answer = read_answer(sys.stdin)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
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
    dump_json(result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
