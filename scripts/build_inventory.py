"""A deterministic public inventory binds relative output paths to current bytes."""
import hashlib
import json
from pathlib import Path

MAX_FILES = 5000
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024


def inventory(site_dir):
    root = Path(site_dir)
    records, total = [], 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("inventory refuses link-like paths")
        if not path.is_file() or path.name == "content-manifest.json":
            continue
        size = path.stat().st_size
        total += size
        if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES or len(records) >= MAX_FILES:
            raise ValueError("public output exceeds the file count or byte budget")
        records.append({"path": path.relative_to(root).as_posix(), "bytes": size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return records


def run(site_dir, cfg):
    document = {"version": 1, "site": "https://" + cfg["DOMAIN"] + "/",
                "reviewed_date": cfg["LAST_UPDATED"],
                "scope": "Built public files, excluding this manifest. Hashes establish byte identity, not factual verification or authorship.",
                "files": inventory(site_dir)}
    (Path(site_dir) / "content-manifest.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
