"""Fail-closed candidate review and read-only drift exit codes."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from review_build import main, review_candidate, snapshot
from build import build_site_staged, json_block


class ReviewCheckTests(unittest.TestCase):
    def test_check_status_distinguishes_drift_without_changing_report(self):
        for kind in (None, 'added', 'changed', 'removed'):
            with self.subTest(kind=kind):
                report = {'added': [], 'changed': [], 'removed': [], 'status': 'candidate-passed'}
                if kind:
                    report[kind] = [{'path': 'synthetic.txt'}]
                for checked in (False, True):
                    out = io.StringIO()
                    args = ['--json'] + (['--check'] if checked else [])
                    with patch('review_build.load_config', return_value={}), \
                            patch('review_build.review_candidate', return_value=report), \
                            contextlib.redirect_stdout(out):
                        status = main(args)
                    self.assertEqual(status, 2 if checked and kind else 0)
                    self.assertEqual(json.loads(out.getvalue()), report)

    def test_real_first_build_and_identical_candidate_check(self):
        cfg = json.loads((ROOT / 'site.config.example.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template, site = root / 'template', root / 'site'
            shutil.copytree(ROOT / 'template', template)
            for expected in (2, 0):
                before = snapshot(site)
                output = io.StringIO()
                with patch('review_build.load_config', return_value=cfg), \
                        patch('review_build.review_candidate', side_effect=lambda *_: review_candidate(template, site, cfg)), \
                        contextlib.redirect_stdout(output):
                    self.assertEqual(main(['--check', '--json']), expected)
                report = json.loads(output.getvalue())
                self.assertEqual(report['status'], 'candidate-passed')
                self.assertEqual(snapshot(site), before)
                self.assertEqual(bool(report['added']), expected == 2)
                if expected == 2:
                    with contextlib.redirect_stdout(io.StringIO()):
                        build_site_staged(str(template), str(site), dict(cfg, **json_block(cfg)))

    def test_check_failure_still_exits_one(self):
        with patch('review_build.load_config', return_value={}), \
                patch('review_build.review_candidate', side_effect=ValueError('synthetic gate failure')), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                main(['--check', '--json'])
            self.assertEqual(result.exception.code, 1)

    def test_zero_exit_without_valid_passing_gate_document_fails_closed(self):
        cfg = json.loads((ROOT / 'site.config.example.json').read_text(encoding='utf-8'))
        invalid = ('', 'not JSON', '{}', '{"warnings": [], "failures": []}',
                   '{"passed": 1, "warnings": [], "failures": []}',
                   '{"passed": false, "warnings": [], "failures": []}',
                   '{"passed": true, "warnings": [], "failures": ["contradictory"]}')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / 'template'
            shutil.copytree(ROOT / 'template', template)
            site = root / 'site'
            site.mkdir()
            (site / 'keep.txt').write_bytes(b'original')
            before = snapshot(site)
            for stdout in invalid:
                with self.subTest(stdout=stdout), patch('review_build.subprocess.run', return_value=
                        subprocess.CompletedProcess([], 0, stdout, '')):
                    with self.assertRaisesRegex(ValueError, 'candidate quality gate'):
                        review_candidate(template, site, cfg)
                self.assertEqual(snapshot(site), before)
                self.assertFalse(list(root.glob('.site-review-*')))
