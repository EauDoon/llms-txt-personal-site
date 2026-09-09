"""Build twice in temporary directories, audit each, and compare exact bytes."""
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


if __name__ == "__main__":
    verify(TEMPLATE, load_config())
