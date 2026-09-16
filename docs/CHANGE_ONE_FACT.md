# Worked case: change one fact

For a hiring manager or recruiter, a current title should match in the readable
profile and the machine-readable page data. This synthetic case changes only
`JOB_TITLE` in the sample config:

```json
"JOB_TITLE": "Synthetic Staff Engineer"
```

Run the focused reproducer from the repository root:

```bash
python -m unittest tests.test_build.BuildTests.test_one_fact_change_propagates_to_markdown_html_and_json_ld -v
```

The test builds from the existing `template/` into a temporary directory. It
does not write `site.config.json`, `template/`, `example/`, or `site/`.

Observed output from that temporary build:

```text
profile.md
| Current title | Synthetic Staff Engineer |

profile.html
<tr><td>Current title</td><td>Synthetic Staff Engineer</td></tr>

index.html
<title>Your Full Name: Synthetic Staff Engineer at Your Employer | Your City</title>

index.html JSON-LD
Person.jobTitle = "Synthetic Staff Engineer"
```

This proves local propagation and consistency for one config value across
generated Markdown, HTML, and JSON-LD. It does not verify the truth of a title,
subject approval, source quality, indexing, assistant retrieval, or hiring
outcomes. Narrative context, sources, historical roles, and dates still need
manual review and editing where they change.

For a real fork, set `FORK_FACTS_CONFIRMED` to `true` only after the subject
signs every published fact and source. Set `FORK_ABSENCES_CONFIRMED` to `true`
only after checking the stated absences, then run the normal fork, build, and
quality checks.
