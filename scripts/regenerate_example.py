#!/usr/bin/env python3
"""Regenerate example/ from site.config.example.json and template/.

    python scripts/regenerate_example.py           rewrite example/ to match
    python scripts/regenerate_example.py --check   report drift and exit 1

example/ is the checked-in generic build of the sample config, and the test
suite compares it with a fresh build byte for byte. This command is the only
supported way to update it. It always reads site.config.example.json and has
no option to read another config, so it cannot copy a real identity into the
public example. Never hand-edit example/ or sync it from a deployed site.
"""
import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from version import __version__

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CONFIG = ROOT / "site.config.example.json"
TEMPLATE = ROOT / "template"
EXAMPLE = ROOT / "example"


def generate(output):
    """Build the sample config into output exactly as the golden test expects."""
    from build import build_site, json_block
    with SAMPLE_CONFIG.open(encoding="utf-8") as source:
        cfg = json.load(source)
    build_site(str(TEMPLATE), str(output), dict(cfg, **json_block(cfg)))


def _files(directory):
    from build_inventory import descendants
    directory = Path(directory)
    if not directory.exists():
        return set()
    return {path.relative_to(directory) for path in descendants(directory) if path.is_file()}


def differences(generated, example):
    """Name every path whose bytes differ between a fresh build and example/."""
    generated, example = Path(generated), Path(example)
    expected_files, generated_files = _files(example), _files(generated)
    found = ["missing generated file: %s" % path.as_posix()
             for path in sorted(expected_files - generated_files)]
    found.extend("unexpected generated file: %s" % path.as_posix()
                 for path in sorted(generated_files - expected_files))
    for path in sorted(expected_files & generated_files):
        expected = (example / path).read_bytes()
        actual = (generated / path).read_bytes()
        if expected == actual:
            continue
        first_changed = next(
            (offset for offset, (left, right) in enumerate(zip(expected, actual)) if left != right),
            min(len(expected), len(actual)),
        )
        found.append(
            "changed file: %s at byte %d (expected %r, generated %r)"
            % (path.as_posix(), first_changed,
               expected[first_changed:first_changed + 80],
               actual[first_changed:first_changed + 80])
        )
    return found


def mirror(generated, example):
    """Make example/ byte-equal to generated; return added, changed, removed counts."""
    from build import is_link_like
    generated, example = Path(generated), Path(example)
    if os.path.lexists(example) and (is_link_like(example) or not example.is_dir()):
        raise ValueError("refusing to write through link-like or non-directory example/")
    wanted, current = _files(generated), _files(example)
    added = changed = removed = 0
    for path in sorted(wanted):
        data = (generated / path).read_bytes()
        target = example / path
        if path in current:
            if target.read_bytes() == data:
                continue
            changed += 1
        else:
            added += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for path in sorted(current - wanted):
        (example / path).unlink()
        removed += 1
        parent = (example / path).parent
        while parent != example and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return added, changed, removed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    parser.add_argument("--check", action="store_true",
                        help="report differences without writing, and exit 1 if example/ is stale")
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="example-build-") as directory:
            generated = Path(directory) / "site"
            with contextlib.redirect_stdout(io.StringIO()):
                generate(generated)
            if args.check:
                found = differences(generated, EXAMPLE)
                for line in found:
                    print(line)
                if found:
                    print("example/ is stale: run python scripts/regenerate_example.py")
                    return 1
                print("example/ matches a fresh build of site.config.example.json")
                return 0
            added, changed, removed = mirror(generated, EXAMPLE)
    except (OSError, ValueError) as exc:
        print("FAIL %s" % exc, file=sys.stderr)
        return 1
    print("example/ regenerated: %d added, %d changed, %d removed" % (added, changed, removed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
