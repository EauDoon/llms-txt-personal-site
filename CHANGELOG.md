# Changelog

All notable changes to this template are recorded here. The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html). A version describes the public contract: the `site.config.json` keys, the script commands and options, the output layout under `site/`, and the quality gate's default rules. See "Versioning and releases" in the [README](README.md).

## [Unreleased]

### Added

- An article without a `desc` is described by its own first sentence in its `llms.txt` link, the writing directory (`writing.html` and `writing.md`) and the Atom `summary`, the same sentence its meta description already used. They used to publish no description, and the feed an empty `summary`. An article with no sentence gets no `summary` element. Search still shows only an authored `desc`.

### Changed

- The HTML companions render `*emphasis*` and `_emphasis_`, which used to appear with their delimiters, and `**strong**` and emphasis nest in either order. A delimiter that touches a letter, digit or `@` on its outside, follows a backslash, or is written as a character reference stays literal, so `snake_case`, `2*3*4` and `@_handle_` are unchanged. Emphasis now runs after links are parsed, so `**` inside a link destination stays in the `href`, and an image's `alt` text no longer carries `<strong>` markup. Check pages that use a literal pair of `*` or `_` around a word.

### Removed

- Seven unused pieces of code in the build scripts: a `json` import in `render_page`, an `unquote` import in `quality_check.py`, the `meta` half of the front-matter unpack in `build_search`, a `DESCRIPTION_NOISE` pattern in `build_catalog.py` that nothing read, and the `visible_markdown_text`, `ScriptSafeJson` and `markdown_label` wrappers, which only called the function they wrapped. The build output does not change.
- The four scratch reports under `audits/` and the `PROGRESS.md` build log. They came from a dated triage workflow and recorded a superseded state: an old test count, a source layout survey that no longer matches the tree, and a README quick start check for work that is done. Nothing in the repository linked to them, and a reader could take them for the current state of the project. `CHANGELOG.md` is the history.

### Fixed

- A published Markdown page with an uppercase suffix, such as `notes.MD` or `writing/note.Md`, now stops the build with its path. It used to be listed in `sitemap.xml` while missing from `llms-full.txt`, `llms.txt`, search, the feed and the HTML companions, and the quality gate passed it. `article.py review` reports such an article as an error, or as a warning while it is a draft.
- `site.config.json` and the rules file may be saved as UTF-8 with a byte order mark, as Windows PowerShell 5.1 writes them. `build.py`, `quality_check.py`, `verify_build.py`, `review_build.py`, `article.py` and `fork.py` used to stop with "Unexpected UTF-8 BOM".
- Numbered list items separated by blank lines render as one list. Each item used to open its own list, so steps 1, 2 and 3 all displayed as "1.". A numbered list that resumes after a code block or quote keeps its first number through the `start` attribute, and a different bullet after a blank line starts a new list, as in CommonMark.
- A bare URL wrapped in `*` or `_`, such as `*https://example.com/a*`, links to `/a`. The HTML companion used to publish `href="https://example.com/a*"`, an underscore-wrapped URL was not linked at all, and `quality_check.py --live` requested `/a**` for `**https://domain/a**` and failed a correct deployment.
- `quality_check.py` reads `robots.txt` the way crawlers do and ends each line at `#`, as RFC 9309 specifies. `Disallow: / # keep out` under `User-agent: *`, or a `User-agent: * # everyone else` line above `Disallow: /`, used to pass although it blocks every unspecified crawler, and a comment after the `Sitemap:` URL failed a correct file.
- A page whose `Last updated:` label or date is wrapped in Markdown emphasis, such as `**Last updated:** 2026-01-01` or `Last updated: _2026-01-01_`, passes the date check. The quality gate used to read the delimiters as the date and fail the page.
- `quality_check.py` escapes any character its output encoding cannot show instead of stopping with `UnicodeEncodeError`. Windows writes redirected output in the ANSI code page, such as cp1252, so a job title in Polish, Greek or Chinese ended the gate with exit 1 on a correct site, and `review_build.py`, which runs the gate through a pipe, reported a failed candidate.
- `quality_check.py --live` requests the configured `google_html_file` and IndexNow key file on the site. It used to put the origin in front of them twice, requesting `https://yourname.comhttps://yourname.com/google0123456789abcdef.html`, so every deployment that set a verification token failed with "ownership proof missing" although the files were served.

## [1.0.0] - 2026-10-09

The first versioned release. It declares the config keys, script commands, output layout and default gate rules as the public contract, so a change that breaks any of them is a new major version from here on. The behavior changes a fork should check before upgrading are listed under Changed.

### Added

- `scripts/version.py`, the single source of the release version. Every script accepts `--version`, `content-manifest.json` records a `generator` such as `llms-txt-personal-site 1.0.0`, and `quality_check.py --live` sends a versioned User-Agent.
- This changelog, a tag, version and changelog consistency check (`version.py --check-tag` and `--notes`) that runs in every CI job, and a release workflow that publishes a GitHub Release from a `vX.Y.Z` tag with its notes taken from this file.
- `scripts/regenerate_example.py`, the only supported way to update `example/`. It builds the sample config and nothing else, and `--check` lists any drift.
- An optional `SITE_LANGUAGE` config key that sets `<html lang>` on every page and Article `inLanguage`. It defaults to `en`.
- The `verification` config block is now published: `bing_msvalidate` as a `msvalidate.01` meta tag on the homepage, `google_html_file` as that file at the site root, and `indexnow_key` as `<key>.txt` at the site root. Invalid tokens stop the build, and the proof files stay out of `sitemap.xml` and the page checks.
- An optional `quality.local.json` rules file, ignored by Git, or any file passed with `--rules FILE`. It holds forbidden strings, allowed exceptions that each need a reason, and switches for the two writing-style rules. `quality.local.example.json` shows the schema.
- `fork.py` runs the offline artifact audit after the quality gate, as CI does.
- CI runs Linux and Windows on Python 3.11, 3.12, 3.13 and 3.14 with a concurrency group, and Dependabot keeps the pinned actions current.

### Changed

- The shipped Vercel config sets `cleanUrls` to `false`. Vercel had answered every `.html` URL with a 308 redirect to an extensionless path, which contradicted the published canonicals and failed `quality_check.py --live`. Extensionless URLs now return 404 on Vercel, so any link to one must use the `.html` path.
- Published Markdown outside the template root and `writing/` now fails the build. It used to be listed in `sitemap.xml` while missing from `llms-full.txt`, `llms.txt`, search and the feed. A draft in a nested folder under `writing/` is still allowed and never built.
- `quality_check.py` exits 1 with a single failure when `site.config.json` is missing, unreadable, not a JSON object, or has no `DOMAIN`, instead of checking the build against `example.com`. A malformed config is a one-line error in `build.py`, `quality_check.py` and `verify_build.py`.
- `build.py --help` and `verify_build.py --help` print usage instead of building.
- The quality gate scans pages at every depth of the build and no longer exempts root `README.md`, `PROMOTION.md`, `RECOMMENDATIONS.md` and `MONITORING.md`.
- Forbidden strings are matched literally and ignoring case in every text file and file name of the build, dot-directories and URLs included. A hit is reported by entry number and file, never by the matched text.
- The homepage and the 404 page wrap their content in a `main` landmark with a skip link and a visible focus outline, and links there and in articles are underlined instead of being told apart by color alone.
- The host configs add a Content-Security-Policy, `X-Frame-Options` and `Permissions-Policy` header and no longer repeat the CORS header in specific rules (see Security).
- Fonts (`.woff`, `.woff2`, `.ttf`, `.otf`, `.eot`), `.avif` and `.bmp` images, audio, video, `.zip` and `.gz` files in `template/` are copied as binary.
- Python 3.11 is the oldest supported version.

### Removed

- The `FORBIDDEN` and `ALLOWED` lists in `scripts/quality_check.py`. If you typed entries into them, move each forbidden string into the `forbidden` list of `quality.local.json` and each `(pattern, reason)` pair into `allowed` as `{"pattern": "...", "reason": "..."}`, then delete them from the tracked script. A public fork that committed them has published them in its Git history.

### Fixed

- On Python 3.11 the content inventory followed Windows junctions and hashed files outside the build. It now refuses any link-like path on every supported version.
- A template file that is not UTF-8 text stops the build with its path instead of a codec error that names no file.
- A link-like template root ends `build.py` with one error message instead of a traceback.
- The artifact audit parses JSON-LD whose type carries a parameter or a different case, and accepts any spelling of a `data:` image favicon's `rel`.
- `article.py review` reports a nested published article as an error and a nested draft as a warning.
- `LICENSE-CONTENT`, `CONTRIBUTING.md`, `SECURITY.md` and `DOCTRINE.md` now describe the repository as it is.
- The test that keeps `template/` and `example/` generic recognizes reference-identity markers by digest instead of spelling them.

### Security

- All three host configs (`.htaccess`, `_headers` and `vercel.json`) send the same Content-Security-Policy, `X-Frame-Options: DENY` and `Permissions-Policy`, and a test keeps them in step. A fork that adds third-party scripts, fonts or embeds must widen the policy.
- The Agent Card's `Access-Control-Allow-Origin` header is set only by the catch-all rule. Cloudflare Pages had joined the duplicate into `*, *`, which browsers reject. `quality_check.py --live` now fails a published card whose header is not exactly `*`, and warns when the homepage lacks `nosniff` or a Content-Security-Policy.
- Forbidden strings no longer live in a tracked script and never appear in the gate's output.

[Unreleased]: https://github.com/EauDoon/llms-txt-personal-site/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/EauDoon/llms-txt-personal-site/releases/tag/v1.0.0
