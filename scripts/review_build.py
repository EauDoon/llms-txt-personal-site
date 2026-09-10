"""Review exact candidate output changes without replacing the current site."""
import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from build import ROOT, build_site_staged, is_link_like, json_block, load_config, paths_overlap
from build_inventory import MAX_FILE_BYTES, MAX_TOTAL_BYTES, inventory
from check_artifacts import audit


def snapshot(root):
    root = Path(root)
    if not os.path.lexists(root):
        return {}
    if is_link_like(root) or not root.is_dir():
        raise ValueError('current output must be a real directory')
    records = inventory(root)
    manifest = root / 'content-manifest.json'
    if manifest.is_file():
        size = manifest.stat().st_size
        if size > MAX_FILE_BYTES or size + sum(row['bytes'] for row in records) > MAX_TOTAL_BYTES:
            raise ValueError('current output including manifest exceeds the byte budget')
        records.append({'path': manifest.name, 'bytes': size, 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()})
    return {row['path']: row for row in records}


def review_candidate(template, current, cfg):
    current = Path(current).absolute()
    if paths_overlap(os.path.realpath(template), os.path.realpath(current)):
        raise ValueError('template and current output must not overlap')
    before = snapshot(current)
    current_issues = []
    if current.exists():
        try:
            current_issues = audit(current)
        except (OSError, ValueError, TypeError) as exc:
            current_issues = ['current artifact audit: ' + str(exc)]
    with tempfile.TemporaryDirectory(prefix='.site-review-', dir=current.parent) as directory:
        root = Path(directory)
        candidate = root / 'site'
        with contextlib.redirect_stdout(io.StringIO()):
            build_site_staged(str(template), str(candidate), dict(cfg, **json_block(cfg)))
        errors = audit(candidate)
        if errors:
            raise ValueError('candidate artifact audit failed: ' + '; '.join(errors))
        config = root / 'public-config.json'
        config.write_text(json.dumps({key: value for key, value in cfg.items() if key not in {'JSON_LD', 'EMAIL_URI'}}), encoding='utf-8')
        result = subprocess.run([sys.executable, str(Path(ROOT) / 'scripts' / 'quality_check.py'),
                                 '--site', str(candidate), '--config', str(config)], capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise ValueError('candidate quality gate failed:\n' + (result.stdout + result.stderr)[-6000:])
        after = snapshot(candidate)
        if before != snapshot(current):
            raise ValueError('current output changed during review; retry against a stable directory')
        added = [after[name] for name in sorted(after.keys() - before.keys())]
        removed = [before[name] for name in sorted(before.keys() - after.keys())]
        changed = [{'path': name, 'before': before[name], 'after': after[name]}
                   for name in sorted(before.keys() & after.keys()) if before[name] != after[name]]
        warnings = re.search(r'WARNINGS: (\d+)', result.stdout)
        return {'version': 1, 'status': 'candidate-passed',
                'scope': 'Local byte comparison and structural checks, not fact approval or deployment.',
                'candidate_manifest_sha256': after['content-manifest.json']['sha256'],
                'quality_warnings': int(warnings[1]) if warnings else None,
                'current_artifact_issues': current_issues, 'added': added, 'changed': changed, 'removed': removed,
                'unchanged': len(before.keys() & after.keys()) - len(changed)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='emit exact path/byte/hash records as JSON')
    args = parser.parse_args(argv)
    try:
        report = review_candidate(Path(ROOT) / 'template', Path(ROOT) / 'site', load_config())
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, 'Build review failed: %s\n' % exc)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('Candidate passed the quality gate and artifact audit. Current site was not replaced.')
        for kind in ('added', 'changed', 'removed'):
            print('%s: %d' % (kind.title(), len(report[kind])))
            for row in report[kind]:
                print('  ' + row['path'])
        print('Unchanged: %d' % report['unchanged'])
        for issue in report['current_artifact_issues']:
            print('Current output issue: ' + issue)
        print('Candidate manifest SHA-256: ' + report['candidate_manifest_sha256'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
