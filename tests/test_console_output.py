"""Every command survives an output encoding that lacks the text it prints.

Windows writes redirected output, and decodes redirected input, in the ANSI
code page, such as cp1252 on GitHub's Windows runners. PYTHONIOENCODING
reproduces that on any machine.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from console_output import dump_json

TITLE = "Żółw notes"  # "Zolw" with Polish letters; Z-dot and l-stroke are not in cp1252
SLUG = "żółw"
ANSWER = "Ingeniero de señales"


def article(status: str, title: str) -> str:
    return ("<!--\nstatus: %s\ntitle: %s\npublished: 2026-01-01\nupdated: 2026-01-01\n"
            "desc: A short note.\nabout: Notes\n-->\n# %s\n\nA body sentence for the note.\n"
            % (status, title, title))


class Cp1252Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repo = Path(self.directory.name)
        shutil.copytree(ROOT / "scripts", self.repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "template", self.repo / "template")
        shutil.copyfile(ROOT / "site.config.example.json", self.repo / "site.config.json")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def run_script(self, *args: str, stdin: bytes = b"", encoding: str = "cp1252"):
        env = dict(os.environ, PYTHONIOENCODING=encoding)
        env.pop("PYTHONUTF8", None)
        result = subprocess.run([sys.executable, str(self.repo / "scripts" / args[0]), *args[1:]],
                                cwd=self.repo, input=stdin, capture_output=True, env=env, check=False)
        stdout = result.stdout.decode(encoding)
        stderr = result.stderr.decode(encoding)
        self.assertNotIn("Traceback", stderr)
        self.assertNotIn("codec can't", stdout + stderr)
        return result.returncode, stdout, stderr

    def test_article_review_reports_a_non_ascii_title_and_file_name(self) -> None:
        (self.repo / "template" / "writing" / (SLUG + ".md")).write_text(article("draft", TITLE), encoding="utf-8")

        code, stdout, stderr = self.run_script("article.py", "review")
        self.assertEqual(code, 0, stdout + stderr)
        self.assertIn("writing/\\u017có\\u0142w.md [draft]", stdout)

        code, stdout, stderr = self.run_script("article.py", "review", "--json")
        self.assertEqual(code, 0, stdout + stderr)
        report = json.loads(stdout)
        rows = {row["path"]: row for row in report["articles"]}
        self.assertEqual(rows["writing/%s.md" % SLUG]["title"], TITLE)

    def test_build_writes_a_non_ascii_article_file_name(self) -> None:
        (self.repo / "template" / "writing" / (SLUG + ".md")).write_text(article("published", TITLE), encoding="utf-8")

        code, stdout, stderr = self.run_script("build.py")
        self.assertEqual(code, 0, stdout + stderr)
        self.assertIn("wrote writing/\\u017có\\u0142w.html", stdout)
        self.assertTrue((self.repo / "site" / "writing" / (SLUG + ".html")).is_file())

    def test_review_build_json_parses_with_a_non_ascii_path(self) -> None:
        (self.repo / "template" / "writing" / (SLUG + ".md")).write_text(article("published", TITLE), encoding="utf-8")

        code, stdout, stderr = self.run_script("review_build.py", "--json")
        self.assertEqual(code, 0, stdout + stderr)
        report = json.loads(stdout)
        self.assertIn("writing/%s.html" % SLUG, [row["path"] for row in report["added"]])

    def eval_file(self, gold: str) -> Path:
        path = self.repo / "eval.json"
        path.write_text(json.dumps({"version": 1, "questions": [{
            "id": "title", "question": "What is the title?", "gold_answer": gold,
            "source_files": ["example/profile.md"], "must_include": [gold]}]}), encoding="utf-8")
        return path

    def test_scorer_prints_a_non_ascii_gold_answer(self) -> None:
        data = str(self.eval_file("Inżynier"))
        for answer, expected in (("Inżynier", 0), ("Someone else", 1)):
            with self.subTest(answer=answer):
                code, stdout, stderr = self.run_script("score_identity_eval.py", "title", "--data", data,
                                                       stdin=answer.encode("utf-8"))
                self.assertEqual(code, expected, stdout + stderr)
                result = json.loads(stdout)
                self.assertEqual(result["gold_answer"], "Inżynier")
                self.assertEqual(result["passed"], expected == 0)

    def test_scorer_reads_redirected_answers_in_utf8_or_the_stream_encoding(self) -> None:
        # Decoding a UTF-8 file as cp1252 turned "señales" into mojibake
        # and scored a correct answer as missing its required phrase.
        data = str(self.eval_file(ANSWER))
        for label, raw in (("utf-8", ANSWER.encode("utf-8")), ("utf-8 with BOM", b"\xef\xbb\xbf" + ANSWER.encode("utf-8")),
                           ("cp1252", ANSWER.encode("cp1252")), ("crlf", (ANSWER + "\r\n").encode("utf-8"))):
            with self.subTest(encoding=label):
                code, stdout, stderr = self.run_script("score_identity_eval.py", "title", "--data", data, stdin=raw)
                self.assertEqual(code, 0, stdout + stderr)
                self.assertTrue(json.loads(stdout)["passed"])

    def test_scorer_refuses_input_in_neither_encoding(self) -> None:
        data = str(self.eval_file(ANSWER))
        code, stdout, stderr = self.run_script("score_identity_eval.py", "title", "--data", data,
                                               stdin=b"\x81\x8d\xff answer")
        self.assertEqual(code, 2, stdout + stderr)
        self.assertEqual(stdout, "")
        self.assertIn("standard input is not text in UTF-8 or cp1252", stderr)

    def test_utf8_output_is_unchanged(self) -> None:
        data = str(self.eval_file("Inżynier"))
        code, stdout, _ = self.run_script("score_identity_eval.py", "title", "--data", data,
                                          stdin="Inżynier".encode("utf-8"), encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertIn('"gold_answer": "Inżynier"', stdout)


class DumpJsonTests(unittest.TestCase):
    def test_text_the_stream_can_encode_is_printed_as_itself(self) -> None:
        stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", newline="\n")
        dump_json({"title": "Inżynier \U0001f600"}, stream=stream)
        stream.flush()
        text = stream.buffer.getvalue().decode("utf-8")
        self.assertEqual(text, json.dumps({"title": "Inżynier \U0001f600"}, ensure_ascii=False, indent=2) + "\n")

    def test_other_text_is_escaped_as_valid_json(self) -> None:
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="backslashreplace", newline="\n")
        data = {"title": "Inżynier \U0001f600", "city": "São Paulo"}
        dump_json(data, stream=stream)
        stream.flush()
        text = stream.buffer.getvalue().decode("cp1252")
        self.assertEqual(json.loads(text), data)
        self.assertNotIn("\\U0001f600", text)


if __name__ == "__main__":
    unittest.main()
