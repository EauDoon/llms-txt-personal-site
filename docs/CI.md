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
