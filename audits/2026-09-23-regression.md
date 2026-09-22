# llms-txt-personal-site - baseline regression audit (2026-09-23)

Branch: ` imp/portfolio-triage-phase9-2026-09-23 `
Default branch captured at clone: ` main `
Python: Python 3.12.10

## Test results (log-verified)

| target | setup | total | pass | skip | fail | error | exit |
|---|---|---:|---:|---:|---:|---:|---:|
| unittest | system Python + tests/ root; 14 test_*.py files (2 .cjs tests not exercised) | 127 | 125 | 2 | 0 | 0 | 0 |
| **total** | | **127** | **125** | **2** | **0** | **0** | |

## Notes

- Per the portfolio triage plan, this commit is a no-op audit-clear baseline. No source, test, or schema files were modified.
- No PR opened by this pass; the human will open the PR on the GitHub web UI.
- Default branch is untouched. Branch push: ` llms-txt-personal-site ` @ ` imp/portfolio-triage-phase9-2026-09-23 `.

## How counts were captured

Counts were re-read directly from the unittest/pytest summary lines (e.g. ` Ran N tests in Ts ` + ` FAILED (errors=E, skipped=S) `) rather than the upstream parser that missed ` OK (skipped=N) ` formatting. Each target was re-invoked in isolation to confirm the count.

## Verdict

Audit clear. 125/127 pass + 2 skips; 2 .cjs tests skipped (out of scope for unittest discover).

