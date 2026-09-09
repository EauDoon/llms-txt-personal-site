"""Offline build audit: byte inventory, local HTML links, fragments, and metadata."""
import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from build_inventory import inventory


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.errors = set(), [], []
        self.json_text = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        identifier = values.get("id")
        if identifier:
            if identifier in self.ids:
                self.errors.append("duplicate id: " + identifier)
            self.ids.add(identifier)
        for key in ("href", "src"):
            if values.get(key):
                self.links.append(values[key])
        if tag == "script" and values.get("type") == "application/ld+json":
            self.json_text = ""

    def handle_data(self, data):
        if self.json_text is not None:
            self.json_text += data

    def handle_endtag(self, tag):
        if tag == "script" and self.json_text is not None:
            try:
                json.loads(self.json_text)
            except ValueError:
                self.errors.append("invalid JSON-LD")
            self.json_text = None


def audit(site_dir):
    root = Path(site_dir).resolve()
    manifest = json.loads((root / "content-manifest.json").read_text(encoding="utf-8"))
    errors = []
    if manifest.get("version") != 1 or manifest.get("files") != inventory(root):
        errors.append("content inventory differs from current output bytes")
    base = manifest.get("site", "")
    if urlsplit(base).scheme != "https" or not urlsplit(base).hostname:
        return errors + ["invalid manifest site URL"]
    documents = {}
    for path in sorted(root.rglob("*.html")):
        document = Document()
        document.feed(path.read_text(encoding="utf-8"))
        documents[path] = document
        errors.extend("%s: %s" % (path.relative_to(root), error) for error in document.errors)
    for path, document in documents.items():
        page_url = urljoin(base, path.relative_to(root).as_posix())
        for link in document.links:
            try:
                parsed = urlsplit(urljoin(page_url, link))
                if parsed.scheme in {"mailto", "data"}:
                    continue
                if parsed.scheme not in {"http", "https"} or "\\" in link:
                    raise ValueError("unsafe link")
                if parsed.netloc != urlsplit(base).netloc:
                    continue
                decoded = unquote(parsed.path)
                if "\\" in decoded or ":" in decoded or "\x00" in decoded:
                    raise ValueError("unsafe local path")
                target = (root / decoded.lstrip("/")).resolve()
                if not target.is_relative_to(root):
                    raise ValueError("local path escapes output")
                if target.is_dir():
                    target /= "index.html"
                if not target.is_file():
                    raise ValueError("missing local target")
                if parsed.fragment and target in documents and unquote(parsed.fragment) not in documents[target].ids:
                    raise ValueError("missing local fragment")
            except (ValueError, OSError) as exc:
                errors.append("%s: %s (%s)" % (path.relative_to(root), link, exc))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", nargs="?", default=str(Path(__file__).resolve().parents[1] / "site"))
    args = parser.parse_args()
    try:
        errors = audit(args.site)
    except (ValueError, OSError, TypeError) as exc:
        errors = [str(exc)]
    for error in errors:
        print("FAIL " + error)
    print("Artifact audit: %d failure(s)" % len(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
