# llms.txt personal site

[![build](https://img.shields.io/github/actions/workflow/status/EauDoon/llms-txt-personal-site/quality-check.yml?branch=main)](https://github.com/EauDoon/llms-txt-personal-site/actions)
[![license](https://img.shields.io/github/license/EauDoon/llms-txt-personal-site)](https://github.com/EauDoon/llms-txt-personal-site/blob/main/LICENSE)
[![last commit](https://img.shields.io/github/last-commit/EauDoon/llms-txt-personal-site)](https://github.com/EauDoon/llms-txt-personal-site)
[![release](https://img.shields.io/github/v/release/EauDoon/llms-txt-personal-site)](https://github.com/EauDoon/llms-txt-personal-site/releases)

**Publish a personal website that gives AI assistants a clear, consistent source for who you are.**

A biography can drift across old profiles, employer pages, and search results. This template helps you maintain your own reference: sourced facts, dated corrections, verified contact routes, and explicit gaps in the record.

Write in Markdown, keep repeated facts in one JSON config, and build a static site with HTML, an `llms.txt` index, and structured data. The Python tooling uses the standard library. No package installation or application server is required.

**Start with the [generated example](example/), or [build your own site](#build-your-own-site).**

The goal is to make accurate information easier to retrieve and cite. Publishing a site does not guarantee indexing, assistant adoption, correct answers, or recommendations.

## How to use this README

This README serves two readers. Pick the section that matches you.

| If you are... | Read |
| --- | --- |
| Someone forking this template to publish your own personal site | [USER](#user-for-someone-forking-this-template) |
| Someone working on this template repository itself (build tooling, CI, contributing changes upstream) | [FORK-CONTRIBUTOR](#fork-contributor-for-someone-working-on-this-template) |

The intro above and the example link apply to both. Everything below is grouped under one of the two headings.

---

# USER (for someone forking this template)

You want to fork this repository, replace the starter content with your own facts, build a static site, and publish it. The sections below cover what the template produces, how to initialize and customize your fork, how updates flow, and the editorial principles behind the content.

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

Use Git and Python 3.11 or newer (CI tests 3.11 to 3.14 on Linux and Windows). On Windows, use `py -3` in place of `python` if that is how your Python installation is available.

### 1. Initialize your config

```bash
git clone https://github.com/EauDoon/llms-txt-personal-site.git
cd llms-txt-personal-site
python scripts/fork.py --init
```

This creates `site.config.json` from the [sample config](site.config.example.json) without overwriting an existing copy.

### 2. Replace the starter content

Edit `site.config.json` for repeated facts and [`template/`](template/) for narrative content. Replace or remove the example article and sample source entries. If you cannot verify a fact, source, or identifier, omit it or describe the uncertainty. If the site is not written in English, set `SITE_LANGUAGE` to its language tag (for example `de` or `pt-BR`); it becomes the `lang` of every page and the `inLanguage` of every article.

Set `FORK_FACTS_CONFIRMED` to `true` only after the subject has signed off on every published fact and source. Set `FORK_ABSENCES_CONFIRMED` to `true` only after checking the stated absences. These flags record your confirmation; they do not perform verification.

**The config is ignored by Git, but its published fields appear in the generated site.** Include only information intended for public release. Keep credentials out of both the config and templates.

### 3. Build and check

```bash
python scripts/fork.py
```

The fork check reports unchanged sample values, recognized starter text, missing confirmations, and disallowed category-query prompts. It stops before building until those checks pass, then runs the builder, the quality gate, and the offline artifact audit (`check_artifacts.py`) that CI also runs. Review the content yourself too: the checks cannot recognize every unfinished sentence or establish whether a claim is true.

The finished files land in `site/`.

### 4. Publish the output

Review `site/` and deploy its contents at the root of the HTTPS domain in your config. Upload the generated output, including any required dotfiles, rather than the repository or your local config.

The template includes [Apache rules](template/.htaccess), [a `_headers` file](template/_headers), and [Vercel configuration](template/vercel.json) for content types and discovery headers. Use the configuration your host supports and verify the actual responses. The build does not configure hosting or deploy files for you.

All three configs send the same security headers on every response: a Content-Security-Policy that allows only same-origin scripts, inline styles, same-origin requests, and HTTPS or `data:` images, plus `X-Frame-Options: DENY`, a `Permissions-Policy` that turns off the camera, microphone, and geolocation, and `X-Content-Type-Options: nosniff`. The generated pages need nothing more. If you add third-party scripts, fonts, analytics, or embeds, widen the policy in all three files, or browsers will block them. A test keeps the three files in step.

To prove ownership to search engines, put your own tokens under `verification` in `site.config.json`. The build publishes each nonempty value: `bing_msvalidate` as a `msvalidate.01` meta tag on the homepage, `google_html_file` as that file at the site root, and `indexnow_key` as `<key>.txt` at the site root. It refuses a value that is not a plain token, keeps the proof files out of `sitemap.xml` and the page checks, and `--live` confirms the files are served. Do not place proof files in `template/` or `site/` by hand: the first are checked as pages, and the second disappear on the next clean build.

Whatever the host, serve every `.html` file at its own path with a `200` response. Canonical links, `sitemap.xml`, the feed, and `quality_check.py --live` all use the `.html` path, and the live check treats a redirect as a failure. The build does not publish extensionless URLs, so leave options such as Vercel's `cleanUrls` off.

After deployment, run:

```bash
python scripts/quality_check.py --live
```

This makes requests to the configured domain. It checks the deployed responses as well as the local build, rejecting response bodies larger than 20 MiB. A homepage served without `nosniff` or a Content-Security-Policy is reported as a warning, so a deployment made before those headers shipped keeps passing until it is redeployed. A local pass alone does not establish that the host serves the same files or headers.

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

See the [synthetic change-one-fact case](docs/CHANGE_ONE_FACT.md) for a recruiter-facing example with observed Markdown, HTML, and JSON-LD output.

The builder creates output in a clean staging directory. Removed template files cannot linger in the next local build, and a generation failure before promotion preserves the previous output. It rejects template symlinks and Windows junctions. Your deployment process must also remove obsolete remote files.

## What the quality gate checks

The build follows the [llms.txt v2 proposal](https://llmstxt.org/). Its checks cover the index structure, same-site index targets, and discovery links between HTML, Markdown, and `llms.txt`.

HTML pages advertise their Markdown version with `rel="alternate"` and the index with `rel="describedby"`. The supplied hosting rules also expose the index through HTTP `Link` headers.

Every indexable page must also declare a document language, a title, a meta description, and a canonical URL. The builder derives each description from the page's own leading prose rather than a separate string, so a description cannot drift away from the page it describes. A page marked `noindex`, such as `404.html`, is exempt because a search result would never show it.

`python scripts/quality_check.py` reads `site/` and `site.config.json` and exits 1 on any failure. Without a usable config it stops with one failure that names the problem. Each run checks:

1. **Rules.** Forbidden strings from your private rules file, then two writing-style rules: no em or en dashes, and American rather than British spelling for a list of common words (URLs are exempt from spelling). Pages are scanned at every depth.
2. **Fact consistency.** Every address on the site's own domains, every `mailto:` link, and every JSON-LD `email` match the configured `EMAIL`, and the job title is listed for review.
3. **Head metadata.** Language, title, description, and a canonical link to the page's own HTTPS URL.
4. **Structured data.** Every JSON-LD block parses, declares schema.org, and links articles to the homepage's person record.
5. **`llms.txt` v2.** The index structure and same-site targets, and the `describedby` and Markdown `alternate` links on every page.
6. **Agent Card.** A published A2A Agent Card passes validation; none is published by default.
7. **Dates.** `LAST_UPDATED` and every page's "Last updated" line are real calendar dates.
8. **Generated files.** `llms-full.txt` holds the current bytes of every Markdown page, and the search index, `search.md`, and the feed agree with the build.
9. **Sitemap and robots.** `sitemap.xml` lists exactly the public files with the configured date, and `robots.txt` points at it without blocking every crawler.
10. **Live, with `--live` only.** Every link and sitemap URL answers `200` without a redirect, configured verification files are served, Markdown is served inline, the Agent Card headers are right, and missing security headers are reported as warnings.

The rules file is optional. Copy [`quality.local.example.json`](quality.local.example.json) to `quality.local.json`, which Git ignores, or pass another file with `--rules FILE`:

- `forbidden`: strings that must never appear anywhere in the build, such as a private handle or an embargoed name. They are matched literally and ignoring case, in every text file and file name, including `search-index.json`, `content-manifest.json`, and `.well-known/`. A hit is reported by entry number and file, never by its text, so CI logs do not repeat it. Never list them in a tracked file: a public fork publishes everything it commits.
- `allowed`: deliberate exceptions, each a regular expression with a nonempty `reason`. A rule match within 120 characters of an allowed match passes.
- `style`: set `em_dash` or `american_spelling` to `false` to turn that writing-style rule off. Both are on by default.

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

---

# FORK-CONTRIBUTOR (for someone working on this template)

You are improving the shared template itself: build tooling, CI, examples, tests, or upstream documentation. The sections below cover the development workflow, the repository layout, and the license terms that apply when reusing the tooling.

## Development and repository map

To build and check the unchanged generic example after initialization:

```bash
python scripts/build.py
python scripts/quality_check.py
python -m unittest discover -s tests -v
node --test tests/*.test.cjs
```

These direct commands support template development. They do not run the personal-site readiness checks in `fork.py`.

[`example/`](example/) is generated, and the tests compare it with a fresh build of the sample config byte for byte. After any change to `template/`, the builder, or `site.config.example.json`, regenerate it with:

```bash
python scripts/regenerate_example.py --check   # list drift and exit 1 if example/ is stale
python scripts/regenerate_example.py           # rewrite example/ from the sample config
```

That command is the only supported way to update `example/`. It reads only `site.config.example.json`, so it cannot copy a real identity into the public example. Never hand-edit `example/` or sync it from a deployed site.

| Path | What to edit or inspect |
| --- | --- |
| [`site.config.example.json`](site.config.example.json) | Available config fields and their guidance. |
| [`template/`](template/) | Source pages and hosting rules. |
| [`example/`](example/) | Checked-in output from the sample config. |
| [`scripts/`](scripts/) | Build, readiness, quality, HTTP, and evaluation tooling. |
| [`tests/`](tests/) | Regression coverage for the tooling and generated output. |
| [`DOCTRINE.md`](DOCTRINE.md) | The editorial method behind the template. |
| [`docs/CI.md`](docs/CI.md) | CI setup and workflow troubleshooting. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | The local check sequence and the rules for changes. |
| [`SECURITY.md`](SECURITY.md) | How to report a vulnerability and what is in scope. |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed in each release. |

The [GitHub Actions workflow](.github/workflows/quality-check.yml) runs tests, builds the sample site, and checks its output on pushes to `main` and pull requests. For contributions, explain the problem, include a minimal reproduction when relevant, and run these checks. Use synthetic examples; do not include credentials or private biographical details in issues or pull requests.

## Versioning and releases

The template follows [Semantic Versioning](https://semver.org/). [`scripts/version.py`](scripts/version.py) is the only place the version is written; every script's `--version`, the live checker's User-Agent, and the `generator` field of `content-manifest.json` read it there, so a fork can tell which release built its site. Changes are recorded in [CHANGELOG.md](CHANGELOG.md).

- **MAJOR** for a removed or renamed config key, a changed output path or URL, or a default gate rule that fails a site that used to pass.
- **MINOR** for new optional config keys, outputs, or checks that existing sites pass.
- **PATCH** for fixes that change none of the above.

A release is an annotated `vX.Y.Z` tag on `main`. Before tagging, set the version, give the `[Unreleased]` entries a dated `## [X.Y.Z] - YYYY-MM-DD` heading, and run `python scripts/regenerate_example.py`. `python scripts/version.py --check-tag vX.Y.Z` must pass. Pushing the tag runs the [release workflow](.github/workflows/release.yml), which repeats that check and the tests, then publishes a GitHub Release whose notes are that changelog section. The manifest's own `"version": 1` is its file format and changes independently.

## License

Scripts and build tooling use the [MIT License](LICENSE). The README, doctrine, template prose, and example content use [CC0](LICENSE-CONTENT). Preserve the applicable license notices when reusing the tooling.
