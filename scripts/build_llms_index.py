"""Add generated writing links to the concise llms.txt index."""

from __future__ import annotations

import io
import os
import re
from urllib.parse import quote

from build_writing_html import parse_front_matter


MARKER = "<!-- GENERATED WRITING LINKS -->"


def _one_line(value):
    return re.sub(r"\s+", " ", value).strip()


def _safe_label(value):
    """Keep a generated Markdown link label on one unambiguous line."""
    return _one_line(value).replace("[", "&#91;").replace("]", "&#93;")


def run(site_dir, cfg):
    index_path = os.path.join(site_dir, "llms.txt")
    if not os.path.isfile(index_path):
        raise OSError("cannot generate writing links because llms.txt is missing")
    with io.open(index_path, encoding="utf-8") as source:
        index = source.read()
    if index.count(MARKER) != 1:
        raise ValueError("llms.txt must contain exactly one generated-writing marker")

    links = []
    writing_dir = os.path.join(site_dir, "writing")
    if os.path.isdir(writing_dir):
        for filename in sorted(os.listdir(writing_dir)):
            if not filename.endswith(".md"):
                continue
            slug = filename[:-3]
            with io.open(os.path.join(writing_dir, filename), encoding="utf-8") as source:
                metadata, _ = parse_front_matter(source.read())
            title = _safe_label(metadata.get("title") or slug.replace("-", " ").title())
            description = _one_line(metadata.get("desc", ""))
            url = "https://%s/writing/%s.md" % (
                cfg.get("DOMAIN", ""),
                quote(slug, safe="-._~"),
            )
            line = "- [%s](%s)" % (title, url)
            if description:
                line += ": " + description
            links.append(line)

    replacement = ""
    if links:
        replacement = "## Writing\n\n" + "\n".join(links)
    index = index.replace(MARKER, replacement)
    with io.open(index_path, "w", encoding="utf-8", newline="") as output:
        output.write(index)
    print("  indexed %d writing page%s in llms.txt" % (len(links), "" if len(links) == 1 else "s"))
    return len(links)
