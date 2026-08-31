# Progress

## Golden rebuild

- Slice: Build `site.config.example.json` in isolation and require an exact byte match with `example/`.
- Commands run: focused golden test; `python -m unittest discover -s tests -v` via the Python 3.12 launcher, 52 run, 50 passed, and 2 skipped; `python scripts/build.py`, passed; exact `site/` to `example/` byte comparison, passed; `python scripts/quality_check.py`, 0 failures and 0 warnings.
- Pick: ours.
- One remaining gap: none.

## Identity-question eval

- Slice: Add ten identity questions with gold answers copied from `example/`, plus a deterministic scorer for an answer pasted on standard input.
- Commands run: focused identity-eval test, red because `scripts/score_identity_eval.py` did not exist; focused identity-eval test after implementation, 3 passed; `python -m unittest discover -s tests -v` via the Python 3.12 launcher, 55 run, 53 passed, and 2 skipped; `python scripts/build.py`, passed; `python scripts/quality_check.py`, 0 failures and 0 warnings; pasted-answer scorer and exact `site/` to `example/` comparison, passed.
- Pick: ours.
- One remaining gap: none.

## Canonical fact fan-out

- Slice: Make `site.config.json` the single input for repeated title, employer, contact, and absence facts while Markdown remains the narrative source.
- Commands run: focused fan-out test, red because the absence keys were missing and contact URLs were duplicated in `SAME_AS`; focused fan-out test after implementation, passed; golden rebuild and identity-eval regressions, 4 passed; `python -m unittest discover -s tests -v` via the Python 3.12 launcher, 56 run, 54 passed, and 2 skipped; `python scripts/build.py`, passed; `python scripts/quality_check.py`, 0 failures and 0 warnings; exact `site/` to `example/` comparison, passed.
- Pick: ours.
- One remaining gap: none.

## Portable live check

- Slice: Replace the Windows-only `curl.exe` transport so `--live` runs with the Python standard library on Linux CI while preserving the default A2A 404 or 410 guard.
- Commands run: focused portability test, red because `scripts/quality_check.py` still invoked `curl.exe`; focused test after implementation, passed with an empty `PATH` and the disabled-card live guard exercised; focused quality-check module, 3 passed; initial full suite, 57 run, 55 passed, and 2 skipped; `python scripts/build.py`, passed; `python scripts/quality_check.py`, 0 failures and 0 warnings; exact `site/` to `example/` comparison, passed; first critic picked the bar because redirects could hide a stale Agent Card; focused redirect-policy test, red because an explicit no-redirect client was missing; redirect-policy and empty-`PATH` tests after the fix, 2 passed; final `python -m unittest discover -s tests -v` via the Python 3.12 launcher, 58 run, 56 passed, and 2 skipped; final build and quality commands passed with 0 failures and 0 warnings; final exact example comparison passed.
- Pick: ours.
- One remaining gap: none.

## One-sitting fork path

- Slice: Add a fail-closed, one-command fork workflow that initializes without overwriting, names unchanged sample facts and starter evidence, runs build plus quality, and publishes no category-query prompts.
- Commands run: focused fork tests, red with 5 tests and 24 named failures because the fork command and README path were missing and category-query prompts remained in config, templates, and the generated example; focused tests after implementation left only the stale example red; rebuilt and synchronized 9 named example files; focused fork module, 5 passed; sample preflight failed closed with 40 named gaps and built nothing; retained-list and renamed-writing edge tests, red then 2 passed after fixes; complete focused fork module, 7 passed; README house-style check, red on `Licence` then passed after correction; initial `python -m unittest discover -s tests -v` via the Python 3.12 launcher, 65 run, 63 passed, and 2 skipped; initial build, quality, exact example comparison, and category-prompt scan passed; first critic picked the bar because the starter writing link in `template/index.html` made HTML a readiness input; Markdown-driven writing-index regressions, red with 2 failures then 2 passed; full suite named the one derived golden difference; rebuilt and synchronized `example/index.html`; final `python -m unittest discover -s tests -v`, 67 run, 65 passed, and 2 skipped; final build passed; final quality check reported 0 failures and 0 warnings; exact `site/` to `example/` comparison passed; final category-prompt scan and `git diff --check` passed; branch remains 0 commits ahead of `origin/main` against the 100-commit PR limit.
- Pick: ours after the Markdown-driven writing-index correction.
- One remaining gap: none.
