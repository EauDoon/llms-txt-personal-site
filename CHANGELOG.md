# Changelog

All notable changes to this template are recorded here. The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html). A version describes the public contract: the `site.config.json` keys, the script commands and options, the output layout under `site/`, and the quality gate's default rules. See "Versioning and releases" in the [README](README.md).

## [Unreleased]

### Added

- `scripts/version.py`, the single source of the release version. Every script accepts `--version`, `content-manifest.json` records a `generator` such as `llms-txt-personal-site 1.0.0`, and `quality_check.py --live` sends a versioned User-Agent.
- This changelog, a tag, version and changelog consistency check (`version.py --check-tag` and `--notes`) that runs in every CI job, and a release workflow that publishes a GitHub Release from a `vX.Y.Z` tag with its notes taken from this file.
- `scripts/regenerate_example.py`, the only supported way to update `example/`. It builds the sample config and nothing else, and `--check` lists any drift.
- An optional `SITE_LANGUAGE` config key that sets `<html lang>` on every page and Article `inLanguage`. It defaults to `en`.
- The `verification` config block is now published: `bing_msvalidate` as a `msvalidate.01` meta tag on the homepage, `google_html_file` as that file at the site root, and `indexnow_key` as `<key>.txt` at the site root. Invalid tokens stop the build, and the proof files stay out of `sitemap.xml` and the page checks.
- An optional `quality.local.json` rules file, ignored by Git, or any file passed with `--rules FILE`. It holds forbidden strings, allowed exceptions that each need a reason, and switches for the two writing-style rules. `quality.local.example.json` shows the schema.
- A skip link, a `main` landmark, and a visible focus outline on the homepage and the 404 page.
- `fork.py` runs the offline artifact audit after the quality gate, as CI does.
- CI runs Linux and Windows on Python 3.11, 3.12, 3.13 and 3.14 with a concurrency group, and Dependabot keeps the pinned actions current.

### Changed

- The shipped Vercel config sets `cleanUrls` to `false`. Vercel had answered every `.html` URL with a 308 redirect to an extensionless path, which contradicted the published canonicals and failed `quality_check.py --live`. Extensionless URLs now return 404 on Vercel, so any link to one must use the `.html` path.
- Published Markdown outside the template root and `writing/` now fails the build. It used to be listed in `sitemap.xml` while missing from `llms-full.txt`, `llms.txt`, search and the feed. A draft in a nested folder under `writing/` is still allowed and never built.
- `quality_check.py` exits 1 with a single failure when `site.config.json` is missing, unreadable, not a JSON object, or has no `DOMAIN`, instead of checking the build against `example.com`. A malformed config is a one-line error in `build.py`, `quality_check.py` and `verify_build.py`.
- `build.py --help` and `verify_build.py --help` print usage instead of building.
- The quality gate scans pages at every depth of the build and no longer exempts root `README.md`, `PROMOTION.md`, `RECOMMENDATIONS.md` and `MONITORING.md`.
- Forbidden strings are matched literally and ignoring case in every text file and file name of the build, dot-directories and URLs included. A hit is reported by entry number and file, never by the matched text.
- Links on the homepage, the 404 page and articles are underlined instead of being told apart by color alone.
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

[Unreleased]: https://github.com/EauDoon/llms-txt-personal-site/commits/main
