#!/usr/bin/env python3
"""Build a site from template/ + site.config.json into site/.

    python scripts/build.py

Runs four steps:
  1. fill placeholders from site.config.json
  2. generate an HTML companion for every writing/*.md page
  3. concatenate everything into llms-full.txt
  4. generate sitemap.xml from the public files that were built

Then run scripts/quality_check.py before you deploy.
"""
import io, json, os, re, shutil, sys, tempfile

from build_sitemap import validate_last_updated

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "template")
OUT = os.path.join(ROOT, "site")
CONFIG = os.path.join(ROOT, "site.config.json")


def load_config():
    if not os.path.exists(CONFIG):
        sys.exit("No site.config.json. Copy site.config.example.json to site.config.json and fill it in.")
    with io.open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    missing = [k for k in ("DOMAIN", "FULL_NAME", "EMAIL", "JOB_TITLE", "LAST_UPDATED") if not cfg.get(k)]
    if missing:
        sys.exit("site.config.json is missing required keys: %s" % ", ".join(missing))
    domain = cfg["DOMAIN"]
    if (
        not isinstance(domain, str)
        or len(domain) > 253
        or not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in domain.split("."))
    ):
        sys.exit("DOMAIN should be a bare hostname, e.g. yourname.com (no https://)")
    try:
        validate_last_updated(cfg["LAST_UPDATED"])
    except ValueError as exc:
        sys.exit(str(exc))
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


def build_site(template_dir, out_dir, cfg):
    """Build a complete site into an empty staging directory."""
    n = 0
    for dirpath, _, files in os.walk(template_dir):
        rel = os.path.relpath(dirpath, template_dir)
        target_dir = out_dir if rel == "." else os.path.join(out_dir, rel)
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            src = os.path.join(dirpath, f)
            dst = os.path.join(target_dir, f)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf")):
                with open(src, "rb") as a, open(dst, "wb") as b:
                    b.write(a.read())
            else:
                with io.open(src, encoding="utf-8") as source:
                    t = source.read()
                with io.open(dst, "w", encoding="utf-8", newline="") as output:
                    output.write(fill(t, cfg))
            n += 1

    print("  filled %d files into site/" % n)

    leftover = {}
    for dirpath, _, files in os.walk(out_dir):
        for f in files:
            if not f.endswith((".md", ".txt", ".html", ".xml", ".json")):
                continue
            with io.open(os.path.join(dirpath, f), encoding="utf-8", errors="ignore") as source:
                t = source.read()
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
        build_writing_html.run(out_dir, cfg)
    except ImportError:
        print("  (skipped writing/ HTML generation: build_writing_html.py not found)")
    import build_llms_full
    build_llms_full.run(out_dir, cfg)
    import build_sitemap
    build_sitemap.run(out_dir, cfg)


def replace_output(staging_dir, output_dir):
    """Replace only output_dir, restoring the prior build if promotion fails."""
    parent = os.path.dirname(output_dir)
    backup = None
    if os.path.lexists(output_dir):
        if os.path.islink(output_dir) or not os.path.isdir(output_dir):
            raise OSError("refusing to replace site/ because it is not a real directory")
        backup = tempfile.mkdtemp(prefix=".site-backup-", dir=parent)
        os.rmdir(backup)
        os.replace(output_dir, backup)
    try:
        os.replace(staging_dir, output_dir)
    except Exception:
        if backup is not None:
            os.replace(backup, output_dir)
        raise
    if backup is not None:
        try:
            shutil.rmtree(backup)
        except OSError as exc:
            print(
                "  WARNING: new site was promoted, but the previous output "
                "could not be removed at %s: %s" % (backup, exc),
                file=sys.stderr,
            )


def build_site_staged(template_dir, output_dir, cfg):
    """Generate in a sibling staging directory, then promote completed output."""
    parent = os.path.dirname(output_dir)
    os.makedirs(parent, exist_ok=True)
    staging = tempfile.mkdtemp(prefix=".site-build-", dir=parent)
    try:
        build_site(template_dir, staging, cfg)
        replace_output(staging, output_dir)
    finally:
        if os.path.isdir(staging):
            shutil.rmtree(staging)


def main():
    cfg = load_config()
    cfg = dict(cfg, **json_block(cfg))

    if not os.path.isdir(TEMPLATE):
        sys.exit("No template/ directory found.")

    build_site_staged(TEMPLATE, OUT, cfg)

    print("\n  done. Next: python scripts/quality_check.py")


if __name__ == "__main__":
    main()
