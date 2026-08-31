"""Fail-closed, one-sitting setup for a new identity-site fork."""

import argparse
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

CONFIG_KEYS_TO_REPLACE = (
    "DOMAIN",
    "FULL_NAME",
    "GIVEN_NAME",
    "FAMILY_NAME",
    "EMAIL",
    "JOB_TITLE",
    "EMPLOYER",
    "EMPLOYER_URL",
    "EMPLOYER_DESC",
    "CITY",
    "COUNTRY_CODE",
    "COUNTRY_NAME",
    "X_HANDLE",
    "LINKEDIN_SLUG",
    "TAGLINE",
    "SUMMARY",
    "KNOWS_ABOUT",
    "ALUMNI_OF",
    "LAST_UPDATED",
)
COLLECTION_CONFIG_KEYS = ("KNOWS_ABOUT", "ALUMNI_OF")

STARTER_MARKERS = {
    "template/experience.md": (
        "[Describe the current role in two or three subject-approved sentences.]",
        "[Add verified previous roles, newest first, or remove this section.]",
    ),
    "template/focus.md": (
        "[Current work domain]",
        "[Describe the subject's current, factual scope here.]",
        "[Example depth page]",
    ),
    "template/now.md": (
        "**Focus one.**",
        "**Focus two.**",
        "[Describe the boundaries of the current role.]",
    ),
    "template/press.md": (
        "YYYY-MM-DD",
        "[Source name](https://example.com)",
        "[Previous title, previous employer]",
    ),
    "template/products.md": (
        "[Product or program name]",
        "Official page: https://example.com",
        "Fact, with the number stated precisely.",
    ),
    "template/profile.md": ("- Area one", "- Area two", "- Area three"),
}

STARTER_FILES = ("template/writing/example-depth-page.md",)

GLOBAL_STARTER_MARKERS = (
    "# Example Depth Page: Replace This Title",
    "Open with a bolded thesis paragraph",
    "## A section heading that matches a real question",
    "Explain the mechanism. Prefer concrete detail over adjectives.",
    "**Related:** link the other depth pages here.",
)

CATEGORY_QUERY_PHRASES = (
    "who should i talk to about",
    "who can help with",
    "what they are a good first call about",
    "relevant queries:",
    "category questions",
    "domain you want to be found for",
    "category you want to be surfaced for",
)


def load_json(path):
    with io.open(path, encoding="utf-8") as source:
        return json.load(source)


def string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from string_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from string_values(nested)


def initialize(repo=REPO):
    """Copy the sample config once and never overwrite a user's config."""
    repo = Path(repo)
    sample = repo / "site.config.example.json"
    current = repo / "site.config.json"
    if not sample.is_file():
        print("site.config.example.json is missing; nothing was created.")
        return 1
    try:
        with sample.open("rb") as source, current.open("xb") as destination:
            shutil.copyfileobj(source, destination)
    except FileExistsError:
        print("site.config.json already exists; left unchanged.")
        return 1
    print("created site.config.json from the sample")
    print("edit site.config.json and template/, then run: python scripts/fork.py")
    return 0


def readiness_issues(repo=REPO):
    """Name every known sample or unsafe starter value that blocks a fork."""
    repo = Path(repo)
    sample_path = repo / "site.config.example.json"
    current_path = repo / "site.config.json"
    if not sample_path.is_file():
        return ["site.config.example.json is missing"]
    if not current_path.is_file():
        return ["site.config.json is missing; run python scripts/fork.py --init"]
    try:
        sample = load_json(sample_path)
        current = load_json(current_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return ["config is unreadable: %s" % exc]
    if not isinstance(sample, dict) or not isinstance(current, dict):
        return [
            "site.config.example.json and site.config.json must contain JSON objects"
        ]

    issues = []
    for key in CONFIG_KEYS_TO_REPLACE:
        if key not in current:
            issues.append("site.config.json: %s is missing" % key)
        elif key not in COLLECTION_CONFIG_KEYS:
            value = current.get(key)
            if not isinstance(value, str) or not value.strip():
                issues.append("site.config.json: %s must be a nonempty string" % key)
            elif value == sample.get(key):
                issues.append("site.config.json: %s still matches the sample" % key)

    for key in COLLECTION_CONFIG_KEYS:
        if key not in current:
            continue
        sample_values = set(string_values(sample.get(key)))
        retained = sample_values & set(string_values(current.get(key)))
        for value in sorted(retained):
            issues.append(
                "site.config.json: %s retains sample value %r" % (key, value)
            )

    for key in ("FORK_FACTS_CONFIRMED", "FORK_ABSENCES_CONFIRMED"):
        if current.get(key) is not True:
            issues.append("site.config.json: %s must be true" % key)

    for relative, markers in STARTER_MARKERS.items():
        path = repo / relative
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for marker in markers:
            if marker in content:
                issues.append("%s: remove starter marker %r" % (relative, marker))

    for relative in STARTER_FILES:
        if (repo / relative).exists():
            issues.append("%s: replace or remove the starter file" % relative)

    category_sources = [("site.config.json", json.dumps(current))]
    template = repo / "template"
    if template.is_dir():
        template_sources = [
            (
                path.relative_to(repo).as_posix(),
                path.read_text(encoding="utf-8", errors="ignore"),
            )
            for path in sorted(template.rglob("*"))
            if path.is_file()
        ]
        category_sources.extend(template_sources)
        for relative, content in template_sources:
            if relative in STARTER_FILES:
                continue
            for marker in GLOBAL_STARTER_MARKERS:
                if marker in content:
                    issues.append(
                        "%s: remove starter marker %r" % (relative, marker)
                    )
    for relative, content in category_sources:
        lowered = content.casefold()
        for phrase in CATEGORY_QUERY_PHRASES:
            if phrase in lowered:
                issues.append(
                    "%s: remove category-query prompt %r" % (relative, phrase)
                )

    return issues


def run(repo=REPO, runner=subprocess.run):
    """Run fork readiness, then the existing build and quality gates."""
    repo = Path(repo)
    issues = readiness_issues(repo)
    if issues:
        print("fork is not ready:")
        for issue in issues:
            print("  - %s" % issue)
        print("nothing was built")
        return 1

    commands = (
        [sys.executable, str(repo / "scripts" / "build.py")],
        [sys.executable, str(repo / "scripts" / "quality_check.py")],
    )
    for command in commands:
        completed = runner(command, cwd=repo)
        if completed.returncode:
            return completed.returncode
    print("fork ready: site/ was built and passed the quality gate")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Initialize or verify a fail-closed identity-site fork."
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="copy site.config.example.json once without overwriting",
    )
    args = parser.parse_args(argv)
    return initialize() if args.init else run()


if __name__ == "__main__":
    sys.exit(main())
