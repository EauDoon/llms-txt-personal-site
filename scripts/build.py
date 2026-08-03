#!/usr/bin/env python3
"""Build a site from template/ + site.config.json into site/.

    python scripts/build.py

Runs three steps:
  1. fill placeholders from site.config.json
  2. generate an HTML companion for every writing/*.md page
  3. concatenate everything into llms-full.txt

Then run scripts/quality_check.py before you deploy.
"""
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "template")
OUT = os.path.join(ROOT, "site")
CONFIG = os.path.join(ROOT, "site.config.json")


def load_config():
    if not os.path.exists(CONFIG):
        sys.exit("No site.config.json. Copy site.config.example.json to site.config.json and fill it in.")
    with io.open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    missing = [k for k in ("DOMAIN", "FULL_NAME", "EMAIL", "JOB_TITLE") if not cfg.get(k)]
    if missing:
        sys.exit("site.config.json is missing required keys: %s" % ", ".join(missing))
    if cfg["DOMAIN"].startswith("http"):
        sys.exit("DOMAIN should be a bare hostname, e.g. yourname.com (no https://)")
    return cfg


def fill(text, cfg):
    """Replace {{KEY}} with the config value. Scalars only; lists are handled by the caller."""
    def sub(m):
        key = m.group(1)
        val = cfg.get(key)
        if val is None:
            return m.group(0)          # leave unknown tokens visible rather than blanking them
        if isinstance(val, (list, dict)):
            return m.group(0)
        return str(val)
    return re.sub(r"\{\{([A-Z0-9_]+)\}\}", sub, text)


def json_block(cfg):
    """Values that go into JSON-LD need JSON encoding, not plain substitution."""
    return {
        "KNOWS_ABOUT_JSON": json.dumps(cfg.get("KNOWS_ABOUT", []), indent=8)[1:-1].strip(),
        "SAME_AS_JSON": json.dumps(cfg.get("SAME_AS", []), indent=8)[1:-1].strip(),
        "ALUMNI_JSON": ",\n        ".join(
            '{ "@type": "Organization", "name": %s, "sameAs": %s }'
            % (json.dumps(a.get("name", "")), json.dumps(a.get("url", "")))
            for a in cfg.get("ALUMNI_OF", [])
        ),
    }


def main():
    cfg = load_config()
    cfg = dict(cfg, **json_block(cfg))

    if not os.path.isdir(TEMPLATE):
        sys.exit("No template/ directory found.")

    n = 0
    for dirpath, _, files in os.walk(TEMPLATE):
        rel = os.path.relpath(dirpath, TEMPLATE)
        target_dir = OUT if rel == "." else os.path.join(OUT, rel)
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            src = os.path.join(dirpath, f)
            dst = os.path.join(target_dir, f)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf")):
                with open(src, "rb") as a, open(dst, "wb") as b:
                    b.write(a.read())
            else:
                t = io.open(src, encoding="utf-8").read()
                io.open(dst, "w", encoding="utf-8", newline="").write(fill(t, cfg))
            n += 1

    print("  filled %d files into site/" % n)

    leftover = {}
    for dirpath, _, files in os.walk(OUT):
        for f in files:
            if not f.endswith((".md", ".txt", ".html", ".xml", ".json")):
                continue
            t = io.open(os.path.join(dirpath, f), encoding="utf-8", errors="ignore").read()
            for m in re.finditer(r"\{\{([A-Z0-9_]+)\}\}", t):
                leftover.setdefault(m.group(1), set()).add(f)
    if leftover:
        print("\n  UNFILLED PLACEHOLDERS (add these keys to site.config.json):")
        for k, where in sorted(leftover.items()):
            print("    {{%s}}  in %s" % (k, ", ".join(sorted(where))[:60]))
    else:
        print("  no unfilled placeholders")

    # steps 2 and 3
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import build_writing_html
        build_writing_html.run(OUT, cfg)
    except ImportError:
        print("  (skipped writing/ HTML generation: build_writing_html.py not found)")
    import build_llms_full
    build_llms_full.run(OUT, cfg)

    print("\n  done. Next: python scripts/quality_check.py")


if __name__ == "__main__":
    main()
