# Contributing

Thanks for your interest in this repository.

## This is a Template

This repository is a personal site template. Contributors are expected to fork it for their own use rather than committing directly to this upstream copy. Issues and pull requests against the template itself are welcome for changes that improve the shared baseline.

## How to Contribute

1. Fork the repository.
2. Create a feature branch from the default branch.
3. Make focused changes. Keep the diff small and the commit history clean.
4. Open a pull request against the upstream repository with a clear description.
5. Respond to review feedback promptly.

## Pull Request Expectations

- One logical change per pull request.
- Include a short summary of the change and the motivation.
- Update documentation when behavior or setup changes.
- Avoid unrelated refactors, formatting churn, or dependency bumps.

## Local Setup

The tooling uses only the Python standard library, so there is nothing to install. You need Git, Python 3.11 or newer, and Node.js 22 or newer for the browser-search tests. Run the same checks as CI from the repository root:

```bash
python -m unittest discover -s tests
node --test tests/*.test.cjs
python -c "import shutil; shutil.copyfile('site.config.example.json', 'site.config.json')"
python scripts/build.py
python scripts/quality_check.py
python scripts/check_artifacts.py
python scripts/verify_build.py
python scripts/regenerate_example.py --check
```

Preview the build with `python -m http.server 8000 --bind 127.0.0.1 --directory site` and open `http://127.0.0.1:8000`. On Windows, use `py -3` in place of `python` if that is how Python is installed.

## Rules for Changes

- Keep Python 3.11 working. CI tests 3.11 to 3.14 on Linux and Windows.
- Never hand-edit `example/` and never copy a real site into it. After changing `template/`, the builder, or the sample config, run `python scripts/regenerate_example.py` and commit the result.
- Use synthetic data in issues, pull requests, tests, and examples. Do not post real biographical details, credentials, private handles, or the contents of a private `quality.local.json`.

## Reporting Bugs

Open a GitHub issue with reproduction steps, expected behavior, and actual behavior. Screenshots help when the issue is visual.

## Code of Conduct

Be respectful. Assume good faith. Keep feedback specific and actionable.
