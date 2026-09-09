# Writing, discovery, and build review

Write articles in `template/writing/*.md`. The builder creates an HTML companion, a writing directory at `/writing.html`, a local search at `/search.html`, and an Atom feed at `/feed.xml`. The directory and search both have Markdown companion indexes. Removing an article removes it from the next complete build.

Article metadata is optional and appears in a leading HTML comment:

```markdown
<!--
title: Your article title
desc: A factual one-sentence summary.
about: First topic, Second topic
published: 2026-01-01
updated: 2026-01-02
-->
# Your article title
```

Use only dates you can support. Dates must be real calendar dates in `YYYY-MM-DD` format, and publication cannot follow the updated date. Without `published`, no publication date is asserted. Without `updated`, Article metadata and Atom use the configured site review date, `LAST_UPDATED`. Midnight UTC in Atom encodes a date, not an observed publication time. The feed is a summary feed and does not retain deleted entries.

Headings receive unique section links and an on-page outline. Fenced code blocks preserve literal text, including HTML examples. Raw HTML in Markdown is escaped. This is a deliberately small Markdown renderer, not a complete CommonMark implementation. Backtick fences, headings, simple lists, links, quotes, and simple tables are supported. Article tables scroll horizontally, keyboard users can skip navigation, and printing removes the outline.

Search matches a literal phrase against titles and the first 100,000 characters of each published Markdown page. It runs in the browser without analytics or an external search service. The generated index is public, like the source pages. Guidance comments are omitted. Without JavaScript or if the index fails to load, the page still lists links to all indexed pages. Clear search restores all results. Search does not establish factual accuracy or rank authority.

After building, run:

```bash
python scripts/quality_check.py
python scripts/check_artifacts.py
python scripts/verify_build.py
```

The artifact audit compares every output file with `content-manifest.json`, validates article JSON-LD, and checks HTML local links and fragment targets. It makes no network requests and does not check external URLs or validate the truth of claims. The manifest deliberately excludes itself. Its hashes identify exact bytes, not authorship, signatures, or independent verification.

The reproducibility check builds twice in temporary directories and removes them afterward. It leaves your existing `site/` unchanged. CI runs both checks. Builds reject overlapping template/output paths, link-like source paths, more than 5,000 source/output files, individual files over 20 MiB, or total source/output bytes over 100 MiB. These are static personal-site budgets, not a sandbox for untrusted Python or template code.

Preview locally with `python -m http.server 8000 --bind 127.0.0.1 --directory site`, then open `http://127.0.0.1:8000`. Test search, clear, empty results, article section links, source links, and a narrow mobile viewport. Stop the server with Ctrl+C. Before deployment, confirm the generated facts and public inventory yourself. Hosting, cache behavior, and deployed content types require separate live verification.
