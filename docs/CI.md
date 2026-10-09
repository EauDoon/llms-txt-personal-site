# Continuous integration

The [canonical workflow](../.github/workflows/quality-check.yml) runs on
pushes to `main` and pull requests. Its matrix covers Linux and Windows on
Python 3.11, 3.12, 3.13 and 3.14, eight jobs named `check (<os>, <python>)`,
with Node.js 22 for the browser-search tests. Python 3.11 is the oldest
supported version. Every job runs the Python and browser-search regressions,
builds the sample site, and runs the quality gate. A failing gate fails the
build. Jobs time out after 15 minutes, because Windows on the newest Python is
the slowest leg.

A concurrency group keyed on the branch cancels a superseded pull request run
when a newer commit is pushed. Runs on `main` are never cancelled, so every
merge keeps a complete record.

The workflow actions are pinned to full commit SHAs with the release tag in a
comment. [Dependabot](../.github/dependabot.yml) opens one grouped pull request
a week when any pinned action has a newer release. `main` has no branch
protection, so read that pull request's checks before merging it.

The [release workflow](../.github/workflows/release.yml) runs only when a
`vX.Y.Z` tag is pushed. It checks that the tag equals `v` plus the version in
`scripts/version.py`, that the version is final, and that `CHANGELOG.md` has a
dated section for it, then runs the Python tests on Linux and publishes a
GitHub Release with that section as its notes. Its job alone gets `contents:
write`; everything else stays read-only. A tag created with the workflow's
own `GITHUB_TOKEN` does not trigger workflows, so push release tags with your
own credentials. If the workflow fails after the tag exists, publish by hand:

```bash
python scripts/version.py --notes X.Y.Z > notes.md
gh release create vX.Y.Z --verify-tag --title vX.Y.Z --notes-file notes.md
```

`tests/test_version.py` runs in every CI job, so a version, changelog, or
manifest generator that disagree fails the pull request before a tag exists.

CI also runs `check_artifacts.py` to validate current bytes and local HTML links,
and `verify_build.py` to compare two temporary builds. See [Writing and build
review](WRITING.md) for the exact scope and local commands.

Use that file's Git history to recover a deleted workflow. There is no second
copy to drift from the tests or security settings used by CI. Windows tests
exercise real junction rejection and output replacement; environments that
cannot create a junction or symlink report an explicit skip, not a pass for
that check.

## If your fork cannot push the workflow

GitHub refuses to let an OAuth app create or update anything under
`.github/workflows/` unless the token carries the `workflow` scope. The error
reads *"refusing to allow an OAuth App to create or update workflow"*.

```bash
gh auth refresh -s workflow
```

Then push again. This is a permission on your token, not a problem with the
file.

**If `gh auth refresh` fails with "received credentials for <other name>",**
your GitHub account was renamed and the local gh config still holds the old
username. Use `gh auth login -s workflow` instead, then
`gh auth logout -u <old-name>` to clear the stale entry.
