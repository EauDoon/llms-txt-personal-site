from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class HostingConfigTests(unittest.TestCase):
    def test_vercel_serves_html_at_its_own_path(self) -> None:
        config = json.loads((TEMPLATE / "vercel.json").read_text(encoding="utf-8"))
        self.assertIn("cleanUrls", config, "keep the cleanUrls decision explicit")
        self.assertIsNot(
            config["cleanUrls"],
            True,
            "cleanUrls makes Vercel 308-redirect every .html URL to an extensionless "
            "path, but canonicals (quality_check.py head metadata), sitemap.xml, the "
            "feed and the --live check, which follows no redirects, all publish "
            "and request the .html path",
        )
        self.assertIsNot(config.get("trailingSlash"), True,
                         "a trailing-slash redirect would also move every published URL")


if __name__ == "__main__":
    unittest.main()
