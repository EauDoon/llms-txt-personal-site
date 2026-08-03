# Continuous integration

`github-actions-quality-check.yml` in this directory runs the build and the
quality gate on every push and pull request. It is not installed by default.

To enable it in your fork:

```bash
mkdir -p .github/workflows
cp docs/github-actions-quality-check.yml .github/workflows/quality-check.yml
git add .github/workflows/quality-check.yml
git commit -m "Enable CI"
git push
```

If the push is rejected with *"refusing to allow an OAuth App to create or
update workflow"*, your token lacks the `workflow` scope. Fix it with:

```bash
gh auth refresh -s workflow
```

Then push again. This is a GitHub permission on your token, not a problem with
the file.
