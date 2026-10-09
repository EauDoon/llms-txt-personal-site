"""The template's release version, written down in this one place.

    python scripts/version.py                    print the version
    python scripts/version.py --check-tag v1.2.3 confirm a tag is releasable
    python scripts/version.py --notes 1.2.3      print that release's notes

Every CLI's --version, the live checker's User-Agent and the generator field
of content-manifest.json read it from here. The file-format versions inside
the manifest, the review reports and the eval data are separate and stay 1.

A tag is releasable when it is "v" plus this version, the version has no
pre-release part, and CHANGELOG.md has a dated "## [X.Y.Z] - YYYY-MM-DD"
section for it. The release workflow runs --check-tag and takes the release
notes from --notes.
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

PROJECT = "llms-txt-personal-site"
__version__ = "1.0.0-dev"

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
# SemVer 2.0.0, from semver.org.
SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)
HEADING = re.compile(r"^## \[([^\]]+)\](?: - (\S+))?[ \t]*$", re.M)


def parse_semver(value):
    """Return a sort key for a SemVer string, or raise ValueError."""
    match = SEMVER.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ValueError("%r is not a SemVer 2.0.0 version" % (value,))
    major, minor, patch, prerelease = (match.group(1), match.group(2), match.group(3), match.group(4))
    # A pre-release sorts before its release; numeric identifiers sort below
    # alphanumeric ones and compare as numbers.
    identifiers = tuple((0, int(part), "") if part.isdigit() else (1, 0, part)
                        for part in prerelease.split(".")) if prerelease else ()
    return int(major), int(minor), int(patch), 0 if prerelease else 1, identifiers


def is_prerelease(value):
    return bool(SEMVER.fullmatch(value).group(4))


def sections(text):
    """Return (version, date or None, body) for every "## [...]" section."""
    matches = list(HEADING.finditer(text))
    found = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end]
        # Link reference definitions close the file; they are not notes.
        body = re.split(r"^\[[^\]]+\]: \S+[ \t]*$", body, maxsplit=1, flags=re.M)[0]
        found.append((match.group(1), match.group(2), body.strip("\n")))
    return found


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def release_notes(text, version):
    """Return the notes of one dated release section, or raise ValueError."""
    for name, stamp, body in sections(text):
        if name == version:
            if not valid_date(stamp):
                raise ValueError("CHANGELOG.md section [%s] has no valid YYYY-MM-DD date" % version)
            if not body.strip():
                raise ValueError("CHANGELOG.md section [%s] is empty" % version)
            return body.strip() + "\n"
    raise ValueError("CHANGELOG.md has no [%s] section" % version)


def tag_problems(tag, version, text):
    """Return every reason the tag cannot be released from this tree."""
    problems = []
    if tag != "v" + version:
        problems.append("tag %s does not match version %s (expected v%s)" % (tag, version, version))
    try:
        parse_semver(version)
        if is_prerelease(version):
            problems.append("version %s is a pre-release; set a final version before tagging" % version)
    except ValueError as exc:
        problems.append(str(exc))
    try:
        release_notes(text, version)
    except ValueError as exc:
        problems.append(str(exc))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check-tag", metavar="TAG", help="exit 1 unless TAG can be released from this tree")
    action.add_argument("--notes", metavar="X.Y.Z", help="print the CHANGELOG.md section for one release")
    parser.add_argument("--changelog", type=Path, default=CHANGELOG, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.check_tag is None and args.notes is None:
        print(__version__)
        return 0
    try:
        text = args.changelog.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print("FAIL cannot read %s: %s" % (args.changelog, exc), file=sys.stderr)
        return 1
    if args.check_tag is not None:
        problems = tag_problems(args.check_tag, __version__, text)
        for problem in problems:
            print("FAIL %s" % problem, file=sys.stderr)
        if problems:
            return 1
        print("%s can be released as version %s" % (args.check_tag, __version__))
        return 0
    try:
        notes = release_notes(text, args.notes)
        # Write UTF-8 bytes so a redirected notes file is the same on every OS.
        sys.stdout.flush()
        sys.stdout.buffer.write(notes.encode("utf-8"))
    except ValueError as exc:
        print("FAIL %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
