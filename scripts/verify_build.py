"""Build twice in temporary directories, audit each, and compare exact bytes.

    python scripts/verify_build.py

Reads site.config.json and template/. The existing site/ is never touched.
"""
import argparse
import tempfile
from pathlib import Path

from build import TEMPLATE, build_site_staged, json_block, load_config
from check_artifacts import audit
from build_inventory import inventory


def verify(template, cfg):
    with tempfile.TemporaryDirectory(prefix="personal-site-verify-") as directory:
        root = Path(directory)
        outputs = [root / "first", root / "second"]
        for output in outputs:
            build_site_staged(str(template), str(output), dict(cfg, **json_block(cfg)))
            errors = audit(output)
            if errors:
                raise ValueError("Artifact audit failed: " + "; ".join(errors))
        if inventory(outputs[0]) != inventory(outputs[1]) or (outputs[0] / "content-manifest.json").read_bytes() != (outputs[1] / "content-manifest.json").read_bytes():
            raise ValueError("Repeated builds produced different bytes")
    print("Verified two reproducible builds and both offline artifact audits.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)
    cfg = load_config()
    try:
        verify(TEMPLATE, cfg)
    except (ValueError, OSError) as exc:
        print("FAIL %s" % exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
