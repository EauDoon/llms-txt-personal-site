# Continuous integration

CI is **enabled** in this repository. `.github/workflows/quality-check.yml`
builds the site from the template and runs the quality gate on every push and
pull request. A failing gate fails the build.

CI also runs `check_artifacts.py` to validate current bytes and local HTML links,
and `verify_build.py` to compare two temporary builds. See [Writing and build
review](WRITING.md) for the exact scope and local commands.

A copy of the workflow is kept here as `github-actions-quality-check.yml` so it
can be restored if the live one is deleted.

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
