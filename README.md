# llms.txt personal site

**Publish a personal website that gives AI assistants a clear, consistent source for who you are.**

A biography can drift across old profiles, employer pages, and search results. This template helps you maintain your own reference: sourced facts, dated corrections, verified contact routes, and explicit gaps in the record.

Write in Markdown, keep repeated facts in one JSON config, and build a static site with HTML, an `llms.txt` index, and structured data. The Python tooling uses the standard library. No package installation or application server is required.

**Start with the [generated example](example/), or [build your own site](#build-your-own-site).**

The goal is to make accurate information easier to retrieve and cite. Publishing a site does not guarantee indexing, assistant adoption, correct answers, or recommendations.

## What it builds

| Output | Purpose |
| --- | --- |
| [`llms.txt`](example/llms.txt) | A concise index that guides assistants to the relevant source pages. |
| [`llms-full.txt`](example/llms-full.txt) | The site's Markdown content collected into one text file. |
| [`profile.md`](example/profile.md), [`experience.md`](example/experience.md), [`faq.md`](example/faq.md) | Reusable answers about identity, roles, and common questions. |
| [`press.md`](example/press.md), [`products.md`](example/products.md) | Places to document independently published sources and verified product facts. |
| [`contact.md`](example/contact.md), [`now.md`](example/now.md), [`changelog.md`](example/changelog.md) | Contact routing, current work, and a record of updates and corrections. |
| [`writing/`](example/writing/) | Longer Markdown articles with generated HTML companions. |
| [`index.html`](example/index.html), [`sitemap.xml`](example/sitemap.xml) | A human-readable homepage with JSON-LD and a sitemap generated from the build. |
| [`writing.html`](example/writing.html), [`search.html`](example/search.html) | A generated writing directory and local full-text search with static page-list fallback. |
| [`feed.xml`](example/feed.xml), [`content-manifest.json`](example/content-manifest.json) | An Atom writing feed and a deterministic inventory of exact output bytes. |

The example is generic starter content, not a verified biography or a site ready to publish as your own.

See [writing and build review](docs/WRITING.md) for article dates, supported Markdown, search limits, offline link audits, and reproducible builds.

The publishing workflow now includes draft-first article creation, a read-only editorial report, and an exact candidate-build change review. Core pages have readable HTML companions; writing is browsable by declared dates and authored topics, with related-article links and shareable filtered search.

```bash
python scripts/article.py new field-notes --title "Field notes" --topic Research
python scripts/article.py review
python scripts/review_build.py
```

The new article remains excluded from every public build until its leading metadata says `status: published`. Review its facts, sources, metadata, and candidate output before that transition. Existing articles without status keep their published behavior. See the writing guide for limits and exact commands; these tools do not configure hosting or publish remotely.

## Build your own site

Use Git and Python 3.12, the version used by this repository's CI. On Windows, use `py -3` in place of `python` if that is how your Python installation is available.

### 1. Initialize your config

```bash
git clone https://github.com/EauDoon/llms-txt-personal-site.git
cd llms-txt-personal-site
python scripts/fork.py --init
```

This creates `site.config.json` from the [sample config](site.config.example.json) without overwriting an existing copy.

### 2. Replace the starter content

Edit `site.config.json` for repeated facts and [`template/`](template/) for narrative content. Replace or remove the example article and sample source entries. If you cannot verify a fact, source, or identifier, omit it or describe the uncertainty.

Set `FORK_FACTS_CONFIRMED` to `true` only after the subject has signed off on every published fact and source. Set `FORK_ABSENCES_CONFIRMED` to `true` only after checking the stated absences. These flags record your confirmation; they do not perform verification.

**The config is ignored by Git, but its published fields appear in the generated site.** Include only information intended for public release. Keep credentials out of both the config and templates.

### 3. Build and check

```bash
python scripts/fork.py
```

The fork check reports unchanged sample values, recognized starter text, missing confirmations, and disallowed category-query prompts. It stops before building until those checks pass, then runs the builder and quality gate. Review the content yourself too: the checks cannot recognize every unfinished sentence or establish whether a claim is true.

The finished files land in `site/`.

### 4. Publish the output

Review `site/` and deploy its contents at the root of the HTTPS domain in your config. Upload the generated output, including any required dotfiles, rather than the repository or your local config.

The template includes [Apache rules](template/.htaccess), [a `_headers` file](template/_headers), and [Vercel configuration](template/vercel.json) for content types and discovery headers. Use the configuration your host supports and verify the actual responses. The build does not configure hosting or deploy files for you.

After deployment, run:

```bash
python scripts/quality_check.py --live
```

This makes requests to the configured domain. It checks the deployed responses as well as the local build. A local pass alone does not establish that the host serves the same files or headers.

## How updates work

```text
site.config.json + template/
             |
             v
      scripts/build.py
             |
             v
           site/
             |
             v
   scripts/quality_check.py
```

Repeated fields such as title, employer, contact details, and checked absence statements come from the config. The builder inserts them into Markdown, HTML, and JSON-LD; LinkedIn and X fields also supply the structured `sameAs` links.

For example, after a verified role change, update the title and employer fields once, revise any historical or narrative passages that need context, update the date, and rebuild. Inspect the resulting profile, FAQ, contact page, and homepage before publishing.

The builder creates output in a clean staging directory. Removed template files cannot linger in the next local build, and a generation failure before promotion preserves the previous output. It rejects template symlinks and Windows junctions. Your deployment process must also remove obsolete remote files.

## What the quality gate checks

The build follows the [llms.txt v2 proposal](https://llmstxt.org/). Its checks cover the index structure, same-site index targets, and discovery links between HTML, Markdown, and `llms.txt`.

HTML pages advertise their Markdown version with `rel="alternate"` and the index with `rel="describedby"`. The supplied hosting rules also expose the index through HTTP `Link` headers.

These are structural and consistency checks. They do not verify sources, prove a biography is accurate, or measure whether an assistant will use it.

## Check answers against your sources

The example includes ten identity questions with reference answers in [`eval/identity_questions.json`](eval/identity_questions.json). List them with:

```bash
python scripts/score_identity_eval.py --list
```

To score an answer, run the command below, paste the answer, then end standard input with Ctrl+D on Unix or Ctrl+Z followed by Enter on Windows:

```bash
python scripts/score_identity_eval.py current_title
```

The scorer checks required phrases and known contradictions. It makes no model calls and saves no run or score. Replace the example questions and reference answers with source-backed material for your own site. A passing score still requires human review for unsupported claims.

## Writing principles

The full method is in [DOCTRINE.md](DOCTRINE.md). In practice:

- Attach sources and dates to factual claims, especially product and press entries.
- Keep important facts consistent across pages that may be read in isolation.
- Correct stale claims explicitly and distinguish historical roles from current ones.
- State checked absences narrowly, with a date, rather than claiming something never existed.
- Disambiguate people with the same name and label opinion as opinion.
- Publish only verified contact details, handles, and other identifiers.

The template is designed for identity questions such as "What is this person's current role?" It does not establish expertise, create independent coverage, or guarantee inclusion in answers such as "Who should I talk to about this topic?"

## Optional A2A discovery

Leave A2A disabled for a static biography. This repository does not implement an agent server and does not generate an Agent Card by default.

If the domain fronts a real [A2A v1 service](https://a2a-protocol.org/latest/specification/), add `"A2A_AGENT_CARD_PATH": "agent-card.local.json"` to your local config. Supply a card describing that service's actual interfaces, skills, and security requirements. The suggested filename is ignored by Git, but the validated card is copied into the public build at `/.well-known/agent-card.json`.

The validator checks the card's supported structure, versions, endpoints, and credential-like fields. Live checks compare its bytes and response headers with the local build. With discovery disabled, the live path must return `404` or `410`, which helps catch stale cards after deployment.

Card validation does not test the server's operations, authorization, or JWS signatures. Verify the service independently before advertising it.

## Development and repository map

To build and check the unchanged generic example after initialization:

```bash
python scripts/build.py
python scripts/quality_check.py
python -m unittest discover -s tests -v
```

These direct commands support template development. They do not run the personal-site readiness checks in `fork.py`.

| Path | What to edit or inspect |
| --- | --- |
| [`site.config.example.json`](site.config.example.json) | Available config fields and their guidance. |
| [`template/`](template/) | Source pages and hosting rules. |
| [`example/`](example/) | Checked-in output from the sample config. |
| [`scripts/`](scripts/) | Build, readiness, quality, HTTP, and evaluation tooling. |
| [`tests/`](tests/) | Regression coverage for the tooling and generated output. |
| [`DOCTRINE.md`](DOCTRINE.md) | The editorial method behind the template. |
| [`docs/CI.md`](docs/CI.md) | CI setup and workflow troubleshooting. |

The [GitHub Actions workflow](.github/workflows/quality-check.yml) runs tests, builds the sample site, and checks its output on pushes to `main` and pull requests. For contributions, explain the problem, include a minimal reproduction when relevant, and run these checks. Use synthetic examples; do not include credentials or private biographical details in issues or pull requests.

## License

Scripts and build tooling use the [MIT License](LICENSE). The README, doctrine, template prose, and example content use [CC0](LICENSE-CONTENT). Preserve the applicable license notices when reusing the tooling.
