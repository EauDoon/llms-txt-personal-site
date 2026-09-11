# Writing, discovery, and build review

Before replacing a local build, run `python scripts/review_build.py` (or `--json`). It builds in a temporary directory, runs the real required quality gate and offline artifact audit, then reports added, changed, removed, and unchanged outputs against actual current bytes. The JSON includes path, byte counts, hashes, and the candidate manifest hash. Existing artifact drift is reported separately. Missing `site/` is treated as a first build. The command leaves current output untouched, removes its temporary candidate, and fails if current output changes during review. It never deploys or approves factual claims. Run the regular builder when ready to replace the local output. The quality CLI accepts `--site DIRECTORY --config FILE` for inspecting an explicit candidate; `--live` remains a separate opt-in network check.

Search supports page-type and authored-topic filters, literal text snippets, and shareable `q`, `type`, and `topic` URL parameters. Typing updates the current URL; filter changes and clearing create navigation history, and Back/Forward restore it. Query text remains client-side search input, but a shared or reloaded URL contains that text and may appear in ordinary hosting logs. No analytics service is added. If loading fails or exceeds ten seconds, the original complete page list stays available and Retry fetches fresh data; successful retry restores the chosen filters. Without JavaScript, use that static directory.

Article HTML links to up to three other published articles sharing authored topics. More shared topics sort first; ties retain archive order. The current article and drafts are excluded. This is transparent topic navigation, not an authority or relevance score inferred from personal data. The writing archive remains available when there are no shared-topic matches.

`topics.html` and `topics.md` group published writing by authored `about` metadata. Up to 12 comma-separated topics of 80 characters each are supported. Grouping normalizes whitespace, Unicode composition and case; topic anchors remain stable when articles are reordered. Labels stay escaped literal text. Draft topics are excluded, and no topics are inferred from prose. The Atom feed exposes the same authored categories.

The writing archive orders articles by their explicit `updated` date, or explicit `published` date when no article update is supplied. Articles with neither date follow in title order. Each row distinguishes declared publication/article-update dates from the configured site-date fallback. No publication date is invented for undated work; the Atom feed uses the same article ordering.

Character references are literal text during Markdown parsing: `&#42;` displays `*` without creating emphasis, and `&#124;` displays a pipe without splitting a table. URL safety checks still use decoded destination text. Configured contact addresses encode Markdown delimiters as character references so every accepted local-part character remains literal in readable core pages. Inline and fenced code continue preserving their literal entity spelling.

Core root-level Markdown pages also receive readable HTML companions with source links, section anchors, and an outline. Existing authored HTML companions are preserved. Search points to the HTML companion only when it advertises the matching Markdown source. Root `index`, `writing`, `search`, and `topics` names remain reserved for their existing/generated surfaces. Core pages are not mislabeled as Article structured data.

Run `python scripts/article.py review` to list drafts, published articles, missing summaries/topics/body, declared-date errors, and use of the site review-date fallback. `--json` produces a versioned report for local tooling; `--strict` also returns a failure for incomplete published articles. Draft warnings do not block strict review, but malformed metadata does. This command reads sources without building, changing files, approving facts, or publishing anything.

Start an article with `python scripts/article.py new field-notes --title "Field notes" --description "A sourced summary." --topic Research`. The command creates `template/writing/field-notes.md` as a draft, without inventing publication or review dates. It refuses existing files, unsafe/reserved names, multiline metadata, and link-like directories. Write and review the content before changing its status to published.

Quoted contact routes can be wrapped in matching Markdown emphasis or inline-code delimiters, for example `**'mailto:you@example.com'**`. The checker recognizes paired outer framing in source and rendered prose. It never removes bytes from an actual HTML contact destination or treats an unmatched trailing suffix as formatting.

The configured email supports a plain ASCII dot-atom address: nonempty atoms separated by single dots, a local part of at most 64 characters, and a dotted domain with nonempty DNS-style labels of 1 to 63 ASCII letters, digits, or internal hyphens. Leading/trailing local dots, repeated dots, edge-hyphen labels, quoted local parts, Unicode addresses, single-label hosts, and bracketed address literals are rejected. ASCII punycode domain labels are supported. The complete address is limited to 254 characters (the domain also has a 253-character limit). These are syntax checks only; no DNS lookup, mailbox ownership, or deliverability check is performed. Supported local-part punctuation is percent-encoded in the generated `mailto:` URI so characters such as `?` and `#` remain part of the address. `EMAIL_URI` is derived by the builder and should not be configured separately.

The required quality gate uses the same email syntax. It checks prose addresses on the configured site domain and configured email domain, using complete domain names, and checks every explicit `mailto:` route and JSON-LD `email` field against the configured contact even when its domain differs. Unrelated third-party prose addresses are outside this consistency check. HTML entities, XML, and JSON-LD use their own parsers; only `mailto:` paths, including Markdown/text links, receive one URI-decoding pass. A literal `%2F` in an email local part remains `%2F` in prose and is encoded as `%252F` in the route. Local-part spelling must match exactly; domain case is ignored. This comparison does not establish ownership or deliverability.

Write articles in `template/writing/*.md`. The builder creates an HTML companion, a writing directory at `/writing.html`, a local search at `/search.html`, and an Atom feed at `/feed.xml`. The directory and search both have Markdown companion indexes. Root-page search titles use the first rendered H1's visible text, including supported formatting, links, and literal inline code. Headings inside code or guidance comments are ignored; a page without a rendered H1 uses its filename. Removing an article removes it from the next complete build.

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

Use `status: draft` in that leading comment to exclude an article's Markdown and same-stem HTML companion before any public output is copied. Its bytes do not enter search, feeds, indexes, the full-text bundle, or the manifest. Changing it to `status: published` publishes it; changing it back removes it from the next complete local build. Articles without status retain the legacy published behavior. Status values are exact, and unknown/duplicate metadata fields or malformed status fail the build while preserving the preceding output. Keep metadata in the leading comment, before the H1. Drafts are an editorial convenience, not a private storage area: other assets in `template/` are public, and Git history is separate from build output.

Use only dates you can support. Dates must be real calendar dates in `YYYY-MM-DD` format, and publication cannot follow the updated date. Without `published`, no publication date is asserted. Without `updated`, Article metadata and Atom use the configured site review date, `LAST_UPDATED`. Midnight UTC in Atom encodes a date, not an observed publication time. The feed includes summaries and full visible article text, and does not retain deleted entries.

Headings receive unique section links and an on-page outline. Fenced code blocks preserve literal text, including HTML examples. Raw HTML in Markdown is escaped. This is a deliberately small Markdown renderer, not a complete CommonMark implementation. Backtick fences, headings, simple lists, links, quotes, and simple tables are supported. Article tables scroll horizontally, keyboard users can skip navigation, and printing removes the outline.

Search matches a literal phrase against titles and the first 100,000 characters of each page's rendered text. The index extracts text from the same Markdown renderer as the article. Authored and configured prose entities are decoded once, then safely escaped for their output context. For example, prose `&amp;` displays and searches as `&`; `&amp;lt;` displays and searches as the literal text `&lt;`. Inline and fenced code retain literal entities, so code containing `&amp;` displays and searches as `&amp;`. Metadata follows the prose policy. The browser search has no analytics or external service. The generated index is public, like the source pages. Guidance comments outside code are omitted. Without JavaScript or if the index fails to load, the page still lists links to all indexed pages. Clear search restores all results. Search does not establish factual accuracy or rank authority.

After building, run:

```bash
python scripts/quality_check.py
python scripts/check_artifacts.py
python scripts/verify_build.py
```

The artifact audit compares every output file with `content-manifest.json`, validates article JSON-LD, and checks HTML local links and fragment targets. It makes no network requests and does not check external URLs or validate the truth of claims. The manifest deliberately excludes itself. Its hashes identify exact bytes, not authorship, signatures, or independent verification.

The reproducibility check builds twice in temporary directories and removes them afterward. It leaves your existing `site/` unchanged. CI runs both checks. Builds reject overlapping template/output paths, link-like source paths, more than 5,000 source/output files, individual files over 20 MiB, or total source/output bytes over 100 MiB. These are static personal-site budgets, not a sandbox for untrusted Python or template code.

Preview locally with `python -m http.server 8000 --bind 127.0.0.1 --directory site`, then open `http://127.0.0.1:8000`. Test search, clear, empty results, article section links, source links, and a narrow mobile viewport. Stop the server with Ctrl+C. Before deployment, confirm the generated facts and public inventory yourself. Hosting, cache behavior, and deployed content types require separate live verification.
## Reader and author workflow additions

Search initially renders 25 matches. **Show more results** adds the next 25 and moves keyboard focus to the first newly revealed link. Query/filter changes, browser history, and clear reset the visible batch; the total match count remains announced. Without JavaScript or when loading fails, the complete static page directory remains available.

Search results identify core pages versus writing and display authored article descriptions and topics. Descriptions and topics also participate in text matching. All result text is inserted as text, never HTML. Existing indexes without the optional context fields remain readable.

Search ranks results by the number of query terms found in the title. Equal scores preserve the generated directory order, and an empty query keeps that order. Ranking is a local matching rule, not an authority or factual-confidence score.

Search ignores letter case and Unicode combining accents, so `cafe` finds `Café` and decomposed `Café`. Results retain authored spelling and excerpts. This is normalization, not translation, stemming, or transliteration; topic filters still select the exact normalized authored topic.

Search matches all unquoted words anywhere in a page; double-quoted phrases must appear together. An unfinished opening quote treats the remainder as a phrase. Empty quotes are ignored. Queries remain capped at 200 characters. Run search regressions with `node --test tests/*.test.cjs`.

The Atom feed includes full visible article text as inert `type="text"` content, alongside summaries, dates, and authored topics. Article pages and the writing directory expose a subscription link, and generated reader pages advertise the feed for compatible readers. Drafts remain excluded. External feed-reader behavior requires testing with your chosen reader.

Writing cards and article pages show an approximate reading time, rounded up at 220 whitespace-delimited visible words per minute (minimum one minute). Headings and code count; hidden guidance and metadata do not. This is a reading aid, not a measured duration, and is less useful for languages without word spaces.

Editorial review warns when multiple valid articles (including drafts) share a title after Unicode, case, and whitespace normalization, or when title metadata disagrees with the visible first heading. These are review prompts, not fact-check failures. `review --strict` includes these warnings for published articles.

Use `--published YYYY-MM-DD` and `--updated YYYY-MM-DD` when the dates are known. Dates must be calendar-valid, and publication cannot follow an explicit update date. Neither option changes draft status or schedules publication. Build review still checks dates against the configured site date when no article update date is supplied.

`python scripts/article.py new notes --title "Notes" --body-file notes.md` copies a UTF-8 Markdown body into a new unpublished article. The source stays unchanged. Existing destinations, link-like inputs, oversized files, empty bodies, and leading metadata comments are rejected. Supply metadata through the command options; review imported body text before publication.
