"""Small, dependency-free checks for the llms.txt v2 contract."""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

FILE_LINK = re.compile(
    r"^\s*[-*]\s+\[([^\]]+)\]\((\S+)\)(?:\s*:\s*(.+))?\s*$"
)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _local_path(url: str, expected_domain: str, site_dir: str | os.PathLike[str]):
    """Return a same-site URL's local path, or None for an external URL."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname or ""
    except ValueError:
        return "invalid"
    if hostname.lower() != expected_domain.lower():
        return None
    decoded = unquote(parsed.path)
    if decoded == "/":
        return Path(site_dir).resolve()
    relative = PurePosixPath(decoded.lstrip("/"))
    if (
        not decoded.startswith("/")
        or decoded.startswith("//")
        or "\\" in decoded
        or any(
            ord(character) < 0x20 or ord(character) == 0x7F
            for character in decoded
        )
        or not relative.parts
        or ".." in relative.parts
        or any(re.fullmatch(r"[A-Za-z]:", part) for part in relative.parts)
    ):
        return "invalid"
    try:
        root = Path(site_dir).resolve()
        candidate = root.joinpath(*relative.parts).resolve()
        candidate.relative_to(root)
    except (OSError, ValueError):
        return "invalid"
    return candidate


def markdown_alternate(relative_html: str) -> str:
    """Return the URL advertised for an HTML artifact's Markdown companion."""
    if relative_html == "index.html":
        return "/profile.md"
    if not relative_html.endswith(".html"):
        raise ValueError("expected an HTML artifact path")
    return "/" + quote(relative_html[:-5], safe="/-._~") + ".md"


def validate_llms_txt(
    text: str,
    expected_domain: str | None = None,
    site_dir: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Return human-readable violations of the llms.txt v2 file-list format.

    The proposal only requires an H1. This template additionally requires every
    linked URL to use HTTPS and every same-site link to name an existing
    Markdown or text build artifact.
    """
    text = text.removeprefix("\ufeff")
    lines = text.splitlines()
    issues: list[str] = []
    first = next((line for line in lines if line.strip()), "")
    if not re.fullmatch(r"#\s+[^#].*", first.strip()):
        issues.append("the first nonblank line must be the single H1 title")

    headings = []
    for number, line in enumerate(lines, 1):
        match = HEADING.match(line.strip())
        if match:
            headings.append((number, len(match.group(1)), match.group(2)))
    h1s = [heading for heading in headings if heading[1] == 1]
    if len(h1s) != 1:
        issues.append("the file must contain exactly one H1 title")
    for number, level, _ in headings:
        if level not in (1, 2):
            issues.append("line %d uses H%d; llms.txt file sections use H2" % (number, level))

    current_section: str | None = None
    section_links: dict[str, int] = {}
    seen_sections: set[str] = set()
    seen_urls: set[str] = set()
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        heading = HEADING.match(stripped)
        if heading:
            if len(heading.group(1)) == 2:
                current_section = heading.group(2).strip()
                key = current_section.casefold()
                if key in seen_sections:
                    issues.append("line %d repeats the H2 section %r" % (number, current_section))
                seen_sections.add(key)
                section_links.setdefault(current_section, 0)
            continue
        if current_section is None or not stripped:
            continue
        link = FILE_LINK.fullmatch(line)
        if not link:
            issues.append(
                "line %d must be a Markdown file-list item under H2 %r"
                % (number, current_section)
            )
            continue
        label, url, _ = link.groups()
        section_links[current_section] += 1
        if not label.strip():
            issues.append("line %d has an empty link label" % number)
        if url in seen_urls:
            issues.append("line %d repeats URL %s" % (number, url))
        seen_urls.add(url)
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            issues.append("line %d has an invalid URL" % number)
            continue
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            issues.append("line %d must use an absolute HTTPS URL" % number)
            continue
        if parsed.username or parsed.password:
            issues.append("line %d must not put credentials in a URL" % number)
        if expected_domain and site_dir is not None:
            if (
                parsed.hostname
                and parsed.hostname.lower() == expected_domain.lower()
                and port not in (None, 443)
            ):
                issues.append("line %d must use the canonical HTTPS origin" % number)
            local = _local_path(url, expected_domain, site_dir)
            if local == "invalid":
                issues.append("line %d has an invalid same-site path" % number)
            elif local is not None:
                if parsed.query or parsed.fragment:
                    issues.append("line %d should link directly to the same-site file" % number)
                if local.suffix.lower() not in {".md", ".txt"}:
                    issues.append("line %d does not link to LLM-friendly same-site content" % number)
                elif not local.is_file():
                    issues.append("line %d links to missing build artifact %s" % (number, parsed.path))

    for section, count in section_links.items():
        if not count:
            issues.append("H2 section %r has no file links" % section)
    return issues


# Directories the build writes and lists itself. They are routing pages for
# the writing, topics and search, so llms.txt need not link them.
GENERATED_DIRECTORIES = {"writing.md", "topics.md", "search.md"}


def unlisted_pages(text: str, expected_domain: str, site_dir: str | os.PathLike[str]) -> list[str]:
    """Return the published Markdown pages that no llms.txt file link resolves to.

    The build creates the HTML companion, the llms-full.txt section, the
    sitemap entry and the writing/ links for every page, but the core links in
    llms.txt are written by hand. A page left out is invisible to an agent
    that routes through the index, and nothing else notices. Pages are the
    .md files at the build root and directly under writing/, as the build
    publishes them. Only links in file-list sections count.
    """
    root = Path(site_dir).resolve()
    linked = set()
    in_section = False
    for line in text.removeprefix("﻿").splitlines():
        heading = HEADING.match(line.strip())
        if heading:
            # As in validate_llms_txt, an H2 opens the file list.
            in_section = in_section or len(heading.group(1)) == 2
            continue
        link = FILE_LINK.fullmatch(line) if in_section else None
        if link:
            local = _local_path(link.group(2), expected_domain, root)
            if isinstance(local, Path):
                linked.add(local)
    pages = []
    for directory in (root, root / "writing"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root).as_posix()
            if path.suffix != ".md" or not path.is_file() or relative in GENERATED_DIRECTORIES:
                continue
            if path.resolve() not in linked:
                pages.append(relative)
    return pages


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "link":
            self.links.append({key.lower(): value or "" for key, value in attrs})


def has_link_relation(
    document: str,
    relation: str,
    href: str,
    media_type: str | None = None,
) -> bool:
    """Return whether an HTML document advertises the requested link relation."""
    parser = _LinkParser()
    parser.feed(document)
    for link in parser.links:
        relations = {value.casefold() for value in link.get("rel", "").split()}
        if relation.casefold() not in relations or link.get("href") != href:
            continue
        if media_type is None or link.get("type", "").casefold() == media_type.casefold():
            return True
    return False
