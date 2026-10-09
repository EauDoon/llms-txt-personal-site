from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
# tests/ is not a package, so make its helper importable under discover and
# under `python -m unittest tests.test_build` alike.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import identity_markers
from identity_markers import contains_marker
from build import build_site, build_site_staged, is_link_like, json_block, load_config
from build_llms_full import run as build_llms_full
from build_sitemap import validate_last_updated
from build_writing_html import md_to_html, render_page


class BuildTests(unittest.TestCase):
    def test_config_is_single_source_for_repeated_identity_facts(self) -> None:
        config = json.loads(
            (ROOT / "site.config.example.json").read_text(encoding="utf-8")
        )
        for key in (
            "ABSENCE_EMPLOYMENT_DATES",
            "ABSENCE_RECORDED_MEDIA",
            "ABSENCE_BYLINED_ARTICLE",
        ):
            self.assertIn(key, config)
        self.assertNotIn("SAME_AS", config)

        original_values = {
            config["JOB_TITLE"],
            config["EMPLOYER"],
            config["EMPLOYER_URL"],
            config["EMAIL"],
            "https://www.linkedin.com/in/%s" % config["LINKEDIN_SLUG"],
            "https://x.com/%s" % config["X_HANDLE"],
            config["ABSENCE_EMPLOYMENT_DATES"],
            config["ABSENCE_RECORDED_MEDIA"],
            config["ABSENCE_BYLINED_ARTICLE"],
        }
        config.update(
            {
                "JOB_TITLE": "Example Canonical Role",
                "EMPLOYER": "Example Canonical Employer",
                "EMPLOYER_URL": "https://canonical-employer.example.test",
                "EMAIL": "canonical@canonical-person.example.test",
                "LINKEDIN_SLUG": "canonical-person",
                "X_HANDLE": "canonicalperson",
                "ABSENCE_EMPLOYMENT_DATES": (
                    "No exact employment dates are published in this example. "
                    "Do not infer them."
                ),
                "ABSENCE_RECORDED_MEDIA": "No recorded interview was located",
                "ABSENCE_BYLINED_ARTICLE": "No bylined publication was located.",
            }
        )
        config = dict(config, **json_block(config))

        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "site"
            build_site(str(ROOT / "template"), str(generated), config)

            expected_surfaces = {
                "Example Canonical Role": (
                    "llms.txt",
                    "profile.md",
                    "experience.md",
                    "focus.md",
                    "faq.md",
                    "now.md",
                    "press.md",
                    "index.html",
                    "writing/example-depth-page.md",
                    "writing/example-depth-page.html",
                ),
                "Example Canonical Employer": (
                    "llms.txt",
                    "profile.md",
                    "experience.md",
                    "focus.md",
                    "faq.md",
                    "now.md",
                    "press.md",
                    "contact.md",
                    "index.html",
                    "writing/example-depth-page.md",
                    "writing/example-depth-page.html",
                ),
                "canonical@canonical-person.example.test": (
                    "llms.txt",
                    "profile.md",
                    "faq.md",
                    "now.md",
                    "contact.md",
                    "index.html",
                    "404.html",
                    "writing/example-depth-page.md",
                    "writing/example-depth-page.html",
                ),
                "https://www.linkedin.com/in/canonical-person": (
                    "profile.md",
                    "faq.md",
                    "contact.md",
                    "index.html",
                ),
                "https://x.com/canonicalperson": (
                    "profile.md",
                    "contact.md",
                    "index.html",
                ),
                "https://canonical-employer.example.test": (
                    "faq.md",
                    "contact.md",
                    "index.html",
                ),
                config["ABSENCE_EMPLOYMENT_DATES"]: ("llms.txt",),
                config["ABSENCE_RECORDED_MEDIA"]: ("press.md",),
                config["ABSENCE_BYLINED_ARTICLE"]: ("press.md",),
            }
            for value, surfaces in expected_surfaces.items():
                for surface in surfaces:
                    with self.subTest(value=value, surface=surface):
                        self.assertIn(
                            value,
                            (generated / surface).read_text(encoding="utf-8"),
                        )

            all_text = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in generated.rglob("*")
                if path.is_file()
            )
            for old_value in original_values:
                with self.subTest(old_value=old_value):
                    self.assertNotIn(old_value, all_text)

    def test_one_fact_change_propagates_to_markdown_html_and_json_ld(self) -> None:
        config = json.loads(
            (ROOT / "site.config.example.json").read_text(encoding="utf-8")
        )
        old_title = config["JOB_TITLE"]
        new_title = "Synthetic Staff Engineer"
        config["JOB_TITLE"] = new_title
        config = dict(config, **json_block(config))

        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "site"
            build_site(str(ROOT / "template"), str(generated), config)

            profile_markdown = (generated / "profile.md").read_text(encoding="utf-8")
            profile_html = (generated / "profile.html").read_text(encoding="utf-8")
            index_html = (generated / "index.html").read_text(encoding="utf-8")
            json_ld = json.loads(
                index_html.split(
                    '<script type="application/ld+json">', 1
                )[1].split("</script>", 1)[0]
            )
            all_text = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in generated.rglob("*")
                if path.is_file()
            )

        self.assertIn(
            "| Current title | Synthetic Staff Engineer |",
            profile_markdown,
        )
        self.assertIn(
            "<tr><td>Current title</td><td>Synthetic Staff Engineer</td></tr>",
            profile_html,
        )
        self.assertIn(
            "<title>Your Full Name: Synthetic Staff Engineer at Your Employer | Your City</title>",
            index_html,
        )
        self.assertEqual(json_ld["@graph"][0]["jobTitle"], new_title)
        self.assertEqual(
            json_ld["@graph"][2]["name"],
            "Your Full Name: Synthetic Staff Engineer, Your Employer",
        )

        self.assertNotIn(old_title, all_text)

    def test_json_ld_is_valid_and_script_safe(self) -> None:
        config = json.loads(
            (ROOT / "site.config.example.json").read_text(encoding="utf-8")
        )
        dangerous_summary = 'Quoted "value" & <tag> </script><script>alert(1)</script>'
        config.update(
            {
                "FULL_NAME": 'Example "Person" & Co',
                "SUMMARY": dangerous_summary,
                "KNOWS_ABOUT": ['Payments & identity', 'Safety < reliability'],
                "ALUMNI_OF": [
                    {
                        "name": 'Example "University"',
                        "url": "https://example.test/?a=1&b=2",
                    }
                ],
            }
        )
        config = dict(config, **json_block(config))

        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "site"
            build_site(str(ROOT / "template"), str(generated), config)
            html = (generated / "index.html").read_text(encoding="utf-8")

        match = re.search(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        document = json.loads(match.group(1))
        person = document["@graph"][0]
        self.assertEqual(person["name"], config["FULL_NAME"])
        self.assertEqual(person["description"], dangerous_summary)
        self.assertEqual(person["knowsAbout"], config["KNOWS_ABOUT"])
        self.assertEqual(person["alumniOf"][0]["name"], config["ALUMNI_OF"][0]["name"])
        self.assertNotIn("</script><script>", match.group(1).lower())
        self.assertIn(r"\u003c/script\u003e", match.group(1).lower())

    def test_example_is_exact_rebuild_from_example_config(self) -> None:
        # One comparator: scripts/regenerate_example.py --check reports the
        # same differences and a plain run repairs them.
        import regenerate_example

        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "site"
            regenerate_example.generate(generated)
            differences = regenerate_example.differences(generated, ROOT / "example")

        self.assertEqual(
            differences,
            [],
            "site.config.example.json rebuild differs from example/; run "
            "python scripts/regenerate_example.py:\n" + "\n".join(differences),
        )

    def test_checked_in_example_has_no_reference_identity(self) -> None:
        paths = [ROOT / "site.config.example.json"]
        for directory in (ROOT / "template", ROOT / "example"):
            paths.extend(path for path in sorted(directory.rglob("*")) if path.is_file())
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertFalse(contains_marker(path.read_bytes()))

    def test_marker_digest_scan_detects_normalized_spellings(self) -> None:
        canary = {12: frozenset({hashlib.sha256(b"canarymarker").hexdigest()})}
        with patch.object(identity_markers, "MARKER_DIGESTS", canary):
            for text in (b"Canary_Marker", b"canary-marker", b"prefix CANARY marker suffix"):
                with self.subTest(text=text):
                    self.assertTrue(contains_marker(text))
            for text in (b"", b"canary", b"a clean generic starter page"):
                with self.subTest(text=text):
                    self.assertFalse(contains_marker(text))

    def test_missing_writing_generator_fails_the_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()

            with patch.dict(sys.modules, {"build_writing_html": None}):
                with self.assertRaises(ModuleNotFoundError):
                    build_site(str(template), str(root / "site"), self.config())

    def test_llms_full_includes_custom_top_level_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "profile.md").write_text("# Profile\n", encoding="utf-8")
            (site / "custom.md").write_text("# Custom\n", encoding="utf-8")
            (site / "changelog.md").write_text("# Changelog\n", encoding="utf-8")

            names = build_llms_full(str(site), self.config())

            self.assertEqual(names, ["profile.md", "custom.md", "changelog.md"])
            self.assertIn(
                "# Custom",
                (site / "llms-full.txt").read_text(encoding="utf-8"),
            )

    def config(self, last_updated: str = "2026-08-29") -> dict[str, str]:
        return {
            "DOMAIN": "example.test",
            "FULL_NAME": "Example Person",
            "GIVEN_NAME": "Example",
            "FAMILY_NAME": "Person",
            "EMAIL": "person@example.test",
            "JOB_TITLE": "Example Role",
            "EMPLOYER": "Example Employer",
            "EMPLOYER_URL": "https://employer.example.test",
            "EMPLOYER_DESC": "An example employer used for tests.",
            "CITY": "Example City",
            "COUNTRY_CODE": "EX",
            "COUNTRY_NAME": "Example Country",
            "LINKEDIN_SLUG": "example-person",
            "X_HANDLE": "exampleperson",
            "SUMMARY": "An example person used to test the build.",
            "ABSENCE_EMPLOYMENT_DATES": "No employment dates are published.",
            "ABSENCE_RECORDED_MEDIA": "No recorded media was located",
            "ABSENCE_BYLINED_ARTICLE": "No bylined article was located.",
            "LAST_UPDATED": last_updated,
        }

    def test_unfilled_placeholder_stops_the_build_and_keeps_previous_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir(parents=True)
            (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")
            site = root / "site"

            build_site_staged(str(template), str(site), self.config())
            original = (site / "content-manifest.json").read_bytes()

            (template / "typo.md").write_text(
                "# Typo\n\nLast updated: {{LAST_UPDATED}}\n\nRole: {{JOB_TITEL}}\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError) as raised:
                build_site_staged(str(template), str(site), self.config())

            self.assertIn("JOB_TITEL", str(raised.exception))
            self.assertFalse((site / "typo.md").exists())
            self.assertEqual((site / "content-manifest.json").read_bytes(), original)

    def test_unfilled_placeholder_in_script_and_host_rules_is_not_promoted(self) -> None:
        # The filler rewrites every text file, but the leftover scan only
        # looked at a few extensions, so a token in search.js or .htaccess
        # was published as if it were a fact.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir(parents=True)
            (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")
            site = root / "site"
            build_site_staged(str(template), str(site), self.config())
            original = (site / "content-manifest.json").read_bytes()

            (template / "search.js").write_text("const domain = '{{SITE_HOST}}';\n", encoding="utf-8")
            (template / ".htaccess").write_text("# curl https://{{HOST_NAME}}/profile.md\n", encoding="utf-8")
            with self.assertRaises(ValueError) as raised:
                build_site_staged(str(template), str(site), self.config())

            message = str(raised.exception)
            self.assertIn("SITE_HOST", message)
            self.assertIn("HOST_NAME", message)
            self.assertFalse((site / "search.js").exists())
            self.assertFalse((site / ".htaccess").exists())
            self.assertEqual((site / "content-manifest.json").read_bytes(), original)

    def test_nested_markdown_is_refused_and_keeps_previous_output(self) -> None:
        # The sitemap walks the whole build, but llms-full.txt, llms.txt,
        # search, the feed and the HTML companions read only the root and
        # writing/, so a nested page used to be advertised and then missing.
        for nested in ("writing/2026/nested.md", "guides/a.md", "Writing/x.md"):
            with self.subTest(nested=nested), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                template = root / "template"
                template.mkdir()
                (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")
                site = root / "site"
                build_site_staged(str(template), str(site), self.config())
                before = {path.relative_to(site): path.read_bytes() for path in site.rglob("*") if path.is_file()}

                source = template / nested
                source.parent.mkdir(parents=True)
                source.write_text("# Nested\n\nLast updated: {{LAST_UPDATED}}\n", encoding="utf-8")
                with self.assertRaises(ValueError) as raised:
                    build_site_staged(str(template), str(site), self.config())

                message = str(raised.exception)
                self.assertIn(nested, message)
                self.assertIn("sitemap.xml", message)
                after = {path.relative_to(site): path.read_bytes() for path in site.rglob("*") if path.is_file()}
                self.assertEqual(after, before)
                self.assertEqual(list(root.glob(".site-build-*")), [])
                self.assertEqual(list(root.glob(".site-backup-*")), [])

    def test_nested_writing_draft_still_builds_without_publishing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            (template / "writing" / "drafts").mkdir(parents=True)
            (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")
            (template / "writing" / "drafts" / "idea.md").write_text(
                "<!--\nstatus: draft\n-->\n# Idea\n", encoding="utf-8")
            build_site_staged(str(template), str(root / "site"), self.config())
            self.assertFalse((root / "site" / "writing" / "drafts").exists())

    def test_undecodable_template_text_names_its_path_and_binary_fonts_copy(self) -> None:
        payload = b"wOF2\x00\x01\x80\xff\xfe binary font bytes\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            (template / "assets").mkdir(parents=True)
            (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")
            (template / "assets" / "x.dat").write_bytes(payload)
            with self.assertRaisesRegex(ValueError, r"not UTF-8 text: assets/x\.dat"):
                build_site_staged(str(template), str(root / "site"), self.config())
            self.assertFalse((root / "site").exists())

            (template / "assets" / "x.dat").unlink()
            for name in ("font.woff2", "photo.avif", "clip.webm"):
                (template / "assets" / name).write_bytes(payload)
            build_site_staged(str(template), str(root / "site"), self.config())
            for name in ("font.woff2", "photo.avif", "clip.webm"):
                with self.subTest(name=name):
                    self.assertEqual((root / "site" / "assets" / name).read_bytes(), payload)

    def test_staged_rebuild_removes_renamed_and_deleted_template_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            writing = template / "writing"
            writing.mkdir(parents=True)
            (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")
            retired = template / "retired.md"
            retired.write_text("# Retired\n\nLast updated: {{LAST_UPDATED}}\n", encoding="utf-8")
            old_article = writing / "old-article.md"
            old_article.write_text("# Old article\n\nLast updated: {{LAST_UPDATED}}\n", encoding="utf-8")
            site = root / "site"

            build_site_staged(str(template), str(site), self.config())
            self.assertTrue((site / "retired.md").is_file())
            self.assertTrue((site / "writing" / "old-article.html").is_file())
            self.assertIn("/writing/old-article.html", (site / "sitemap.xml").read_text(encoding="utf-8"))

            retired.unlink()
            old_article.rename(writing / "new-article.md")
            build_site_staged(str(template), str(site), self.config())

            self.assertFalse((site / "retired.md").exists())
            self.assertFalse((site / "writing" / "old-article.md").exists())
            self.assertFalse((site / "writing" / "old-article.html").exists())
            self.assertTrue((site / "writing" / "new-article.md").is_file())
            self.assertTrue((site / "writing" / "new-article.html").is_file())
            sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
            self.assertNotIn("retired.md", sitemap)
            self.assertNotIn("old-article", sitemap)
            self.assertIn("/writing/new-article.md", sitemap)
            self.assertIn("/writing/new-article.html", sitemap)
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    def test_failed_staged_generation_preserves_previous_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")
            site = root / "site"
            build_site_staged(str(template), str(site), self.config())
            before = (site / "sitemap.xml").read_bytes()

            with self.assertRaisesRegex(ValueError, "calendar-valid"):
                build_site_staged(str(template), str(site), self.config("2026-02-30"))

            self.assertEqual((site / "sitemap.xml").read_bytes(), before)
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    def test_locked_backup_cleanup_warns_after_successful_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text("<h1>New site</h1>\n", encoding="utf-8")
            site = root / "site"
            site.mkdir()
            (site / "stale.txt").write_text("old site\n", encoding="utf-8")
            error = io.StringIO()

            with patch("build.shutil.rmtree", side_effect=PermissionError("locked by scanner")):
                with contextlib.redirect_stderr(error):
                    build_site_staged(str(template), str(site), self.config())

            self.assertEqual((site / "index.html").read_text(encoding="utf-8"), "<h1>New site</h1>\n")
            self.assertFalse((site / "stale.txt").exists())
            backups = list(root.glob(".site-backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(
                (backups[0] / "site" / "stale.txt").read_text(encoding="utf-8"),
                "old site\n",
            )
            self.assertIn("new site was promoted", error.getvalue())
            self.assertIn("previous output could not be removed", error.getvalue())
            self.assertIn("locked by scanner", error.getvalue())

    def test_failed_backup_move_removes_reserved_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text(
                "<h1>New site</h1>\n", encoding="utf-8"
            )
            site = root / "site"
            site.mkdir()
            (site / "previous.txt").write_text("previous build\n", encoding="utf-8")
            real_replace = os.replace

            def replace(source: str, destination: str) -> None:
                if os.path.normpath(source) == os.path.normpath(str(site)):
                    raise PermissionError("site locked by scanner")
                real_replace(source, destination)

            with patch("build.os.replace", side_effect=replace):
                with self.assertRaisesRegex(PermissionError, r"site locked"):
                    build_site_staged(str(template), str(site), self.config())

            self.assertEqual(
                (site / "previous.txt").read_text(encoding="utf-8"),
                "previous build\n",
            )
            self.assertFalse((site / "index.html").exists())
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    def test_failed_promotion_and_restore_report_backup_recovery_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text(
                "<h1>New site</h1>\n", encoding="utf-8"
            )
            site = root / "site"
            site.mkdir()
            (site / "previous.txt").write_text("previous build\n", encoding="utf-8")
            real_replace = os.replace

            def replace(source: str, destination: str) -> None:
                source_path = Path(source)
                if source_path.parent.name.startswith(".site-backup-"):
                    raise PermissionError("restore failed")
                if source_path.name.startswith(".site-build-"):
                    raise PermissionError("promotion failed")
                real_replace(source, destination)

            with patch("build.os.replace", side_effect=replace):
                with self.assertRaisesRegex(
                    OSError, r"recover it from .*\.site-backup-.*[\\/]site"
                ) as raised:
                    build_site_staged(str(template), str(site), self.config())

            self.assertFalse(site.exists())
            backups = list(root.glob(".site-backup-*/site"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(
                (backups[0] / "previous.txt").read_text(encoding="utf-8"),
                "previous build\n",
            )
            self.assertIsInstance(raised.exception.__cause__, PermissionError)
            self.assertEqual(str(raised.exception.__cause__), "restore failed")
            self.assertIsInstance(
                raised.exception.__cause__.__context__, PermissionError
            )
            self.assertEqual(
                str(raised.exception.__cause__.__context__), "promotion failed"
            )
            self.assertEqual(list(root.glob(".site-build-*")), [])

    def test_failed_staging_cleanup_preserves_original_error_and_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            site = root / "site"
            error = io.StringIO()

            with patch("build.build_site", side_effect=ValueError("generation failed")):
                with patch(
                    "build.shutil.rmtree",
                    side_effect=PermissionError("staging cleanup failed"),
                ):
                    with contextlib.redirect_stderr(error):
                        with self.assertRaisesRegex(ValueError, r"generation failed"):
                            build_site_staged(str(template), str(site), self.config())

            staging = list(root.glob(".site-build-*"))
            self.assertEqual(len(staging), 1)
            self.assertIn(str(staging[0]), error.getvalue())
            self.assertIn("staging cleanup failed", error.getvalue())
            self.assertIn("the build failed", error.getvalue())

    @unittest.skipUnless(os.name == "nt", "requires native Windows junctions")
    def test_native_junction_source_and_output_preserve_previous_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            (outside / "keep.txt").write_text("must survive\n", encoding="utf-8")
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text("<h1>New site</h1>\n", encoding="utf-8")
            site = root / "site"
            site.mkdir()
            (site / "previous.txt").write_text("previous build\n", encoding="utf-8")
            for link in (template / "linked", root / "linked-output"):
                with self.subTest(location=link.name):
                    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                                            capture_output=True, text=True, timeout=10)
                    if result.returncode:
                        self.skipTest("native junction creation is unavailable in this environment")
                    try:
                        self.assertTrue(is_link_like(link))
                        output = site if link.parent == template else link
                        with self.assertRaises(OSError):
                            build_site_staged(str(template), str(output), self.config())
                        self.assertEqual((outside / "keep.txt").read_text(encoding="utf-8"), "must survive\n")
                        self.assertEqual((site / "previous.txt").read_text(encoding="utf-8"), "previous build\n")
                    finally:
                        os.rmdir(link)
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    @unittest.skipUnless(os.name == "nt", "requires native Windows junctions")
    def test_inventory_refuses_a_native_junction_on_every_python(self) -> None:
        # Path.rglob follows junctions on Python 3.11, so the manifest used to
        # hash files from outside the build there.
        from build_inventory import inventory
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            (outside / "leak.txt").write_text("outside the build\n", encoding="utf-8")
            out = root / "out"
            out.mkdir()
            (out / "a.txt").write_text("inside\n", encoding="utf-8")
            link = out / "linked"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode:
                self.skipTest("native junction creation is unavailable in this environment")
            try:
                with self.assertRaisesRegex(ValueError, "link-like"):
                    inventory(out)
            finally:
                os.rmdir(link)

    def test_inventory_does_not_descend_into_a_junction_like_directory(self) -> None:
        from build_inventory import inventory
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "a.txt").write_text("inside\n", encoding="utf-8")
            linked = out / "linked"
            linked.mkdir()
            (linked / "leak.txt").write_text("outside the build\n", encoding="utf-8")
            self.assertEqual([row["path"] for row in inventory(out)], ["a.txt", "linked/leak.txt"])

            def isjunction(path) -> bool:
                return os.path.normpath(str(path)) == os.path.normpath(str(linked))

            with patch("build.os.path.isjunction", side_effect=isjunction, create=True), \
                    patch.object(Path, "read_bytes", side_effect=AssertionError("hashed a file")):
                with self.assertRaisesRegex(ValueError, "link-like"):
                    inventory(out)

    def test_failed_promotion_restores_previous_output_with_native_moves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text("<h1>New site</h1>\n", encoding="utf-8")
            site = root / "site"
            site.mkdir()
            (site / "previous.txt").write_text("previous build\n", encoding="utf-8")
            real_replace = os.replace

            def replace(source, destination):
                if Path(source).name.startswith(".site-build-"):
                    raise PermissionError("promotion denied")
                return real_replace(source, destination)

            with patch("build.os.replace", side_effect=replace):
                with self.assertRaisesRegex(PermissionError, "promotion denied"):
                    build_site_staged(str(template), str(site), self.config())
            self.assertEqual((site / "previous.txt").read_text(encoding="utf-8"), "previous build\n")
            self.assertFalse((site / "index.html").exists())
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are not supported")
    def test_symlinked_template_file_is_rejected_without_replacing_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text("<h1>New site</h1>\n", encoding="utf-8")
            outside = root / "private.txt"
            outside.write_text("must not be published\n", encoding="utf-8")
            try:
                os.symlink(outside, template / "leak.txt")
            except OSError as exc:
                self.skipTest("cannot create a symlink in this environment: %s" % exc)

            site = root / "site"
            site.mkdir()
            (site / "previous.txt").write_text("previous build\n", encoding="utf-8")

            with self.assertRaisesRegex(
                OSError, r"link-like template path: leak\.txt"
            ):
                build_site_staged(str(template), str(site), self.config())

            self.assertEqual(
                (site / "previous.txt").read_text(encoding="utf-8"),
                "previous build\n",
            )
            self.assertFalse((site / "leak.txt").exists())
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are not supported")
    def test_symlinked_template_root_is_rejected_without_replacing_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            (outside / "index.html").write_text(
                "<h1>must not be published</h1>\n", encoding="utf-8"
            )
            template = root / "template"
            try:
                os.symlink(outside, template, target_is_directory=True)
            except OSError as exc:
                self.skipTest("cannot create a symlink in this environment: %s" % exc)

            site = root / "site"
            site.mkdir()
            (site / "previous.txt").write_text("previous build\n", encoding="utf-8")

            with self.assertRaisesRegex(OSError, r"link-like template root"):
                build_site_staged(str(template), str(site), self.config())

            self.assertEqual(
                (site / "previous.txt").read_text(encoding="utf-8"),
                "previous build\n",
            )
            self.assertFalse((site / "index.html").exists())
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    def test_junction_like_template_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            linked = template / "linked"
            linked.mkdir(parents=True)
            (linked / "private.txt").write_text(
                "must not be published\n", encoding="utf-8"
            )
            site = root / "site"

            def isjunction(path: str) -> bool:
                return os.path.normpath(path) == os.path.normpath(str(linked))

            with patch("build.os.path.isjunction", side_effect=isjunction, create=True):
                with self.assertRaisesRegex(
                    OSError, r"link-like template path: linked"
                ):
                    build_site_staged(str(template), str(site), self.config())

            self.assertFalse(site.exists())
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    def test_reparse_point_fallback_does_not_require_isjunction(self) -> None:
        with patch("build.os.path.islink", return_value=False):
            with patch("build.os.path.isjunction", None, create=True):
                with patch("build.os.lstat") as lstat:
                    lstat.return_value.st_file_attributes = 0x0400
                    self.assertTrue(is_link_like("junction"))

    def test_junction_like_output_directory_is_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text(
                "<h1>New site</h1>\n", encoding="utf-8"
            )
            site = root / "site"
            site.mkdir()
            (site / "previous.txt").write_text("previous build\n", encoding="utf-8")

            def isjunction(path: str) -> bool:
                return os.path.normpath(path) == os.path.normpath(str(site))

            with patch("build.os.path.isjunction", side_effect=isjunction, create=True):
                with self.assertRaisesRegex(OSError, r"not a real directory"):
                    build_site_staged(str(template), str(site), self.config())

            self.assertEqual(
                (site / "previous.txt").read_text(encoding="utf-8"),
                "previous build\n",
            )
            self.assertFalse((site / "index.html").exists())
            self.assertEqual(list(root.glob(".site-build-*")), [])
            self.assertEqual(list(root.glob(".site-backup-*")), [])

    def test_last_updated_requires_an_exact_calendar_date(self) -> None:
        self.assertEqual(validate_last_updated("2024-02-29"), "2024-02-29")
        for value in ("", "2026-02-29", "2026-02-30", "20260829", "2026-8-29", None, 20260829):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "calendar-valid"):
                    validate_last_updated(value)

    def test_domain_must_be_a_bare_hostname(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "site.config.json"
            for domain in (
                "HTTPS://example.test",
                "example.test/path",
                "user@example.test",
                "example.test:443",
                "example..test",
                "-example.test",
                "example-.test",
                "example\\test",
                'example"test',
                "café.test",
                f"{'a' * 64}.test",
            ):
                config_path.write_text(json.dumps({**self.config(), "DOMAIN": domain}), encoding="utf-8")
                with self.subTest(domain=domain), patch("build.CONFIG", str(config_path)):
                    with self.assertRaisesRegex(SystemExit, "bare hostname"):
                        load_config()
            for domain in ("EXAMPLE.TEST", "xn--caf-dma.test"):
                config_path.write_text(json.dumps({**self.config(), "DOMAIN": domain}), encoding="utf-8")
                with self.subTest(domain=domain), patch("build.CONFIG", str(config_path)):
                    self.assertEqual(load_config()["DOMAIN"], domain)

    def test_markdown_link_cannot_inject_html_attributes(self) -> None:
        rendered = md_to_html(
            '[safe](https://example.test/" onmouseover="document.body.dataset.pwned=\'yes\')'
        )

        self.assertNotIn(' onmouseover="', rendered)
        self.assertIn("&quot;", rendered)

    def test_writing_filename_cannot_inject_html_attributes(self) -> None:
        rendered = render_page(
            'bad" onmouseover="alert(1)',
            "# Test\n",
            self.config(),
        )

        self.assertNotIn(' onmouseover="', rendered)
        self.assertIn("bad%22%20onmouseover%3D%22alert%281%29.html", rendered)

    def test_load_config_requires_every_key_json_block_consumes(self) -> None:
        from build import REQUIRED_CONFIG
        for missing_key in ("GIVEN_NAME", "FAMILY_NAME", "EMPLOYER_DESC", "CITY",
                            "COUNTRY_CODE", "COUNTRY_NAME", "SUMMARY"):
            with self.subTest(missing=missing_key):
                incomplete = {k: v for k, v in self.config().items() if k != missing_key}
                with tempfile.TemporaryDirectory() as directory:
                    config_path = Path(directory) / "site.config.json"
                    config_path.write_text(json.dumps(incomplete), encoding="utf-8")
                    with patch("build.CONFIG", str(config_path)):
                        with self.assertRaisesRegex(SystemExit, "missing required keys"):
                            load_config()
                        self.assertIn(missing_key, REQUIRED_CONFIG)

    def cli_repo(self, directory: str, config_text: str | None = None) -> Path:
        repo = Path(directory) / "repo"
        shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "template", repo / "template")
        if config_text is not None:
            (repo / "site.config.json").write_text(config_text, encoding="utf-8")
        return repo

    def run_cli(self, repo: Path, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(repo / "scripts" / script), *args], cwd=repo,
                              capture_output=True, text=True, check=False, timeout=300)

    def test_build_help_prints_usage_and_builds_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.cli_repo(directory, (ROOT / "site.config.example.json").read_text(encoding="utf-8"))
            result = self.run_cli(repo, "build.py", "--help")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("usage:", result.stdout)
            self.assertIn("content-manifest.json", result.stdout)
            self.assertFalse((repo / "site").exists())
            self.assertEqual(list(repo.glob(".site-build-*")), [])

    def test_malformed_config_fails_cleanly_in_every_cli_that_reads_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.cli_repo(directory, '{"DOMAIN": "example.test",')
            (repo / "site").mkdir()
            for script in ("build.py", "quality_check.py", "verify_build.py"):
                with self.subTest(script=script):
                    result = self.run_cli(repo, script)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("not valid JSON", result.stdout + result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_link_like_template_root_fails_build_cli_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.cli_repo(directory, (ROOT / "site.config.example.json").read_text(encoding="utf-8"))
            outside = Path(directory) / "outside-template"
            (repo / "template").rename(outside)
            link = repo / "template"
            try:
                os.symlink(outside, link, target_is_directory=True)
            except OSError:
                if os.name != "nt":
                    self.skipTest("symbolic links are unavailable in this environment")
                made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                                      capture_output=True, text=True, timeout=10)
                if made.returncode:
                    self.skipTest("native junction creation is unavailable in this environment")
            try:
                result = self.run_cli(repo, "build.py")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("link-like template root", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse((repo / "site").exists())
            finally:
                if os.path.islink(link):
                    os.unlink(link)
                else:
                    os.rmdir(link)

    def test_load_config_reports_invalid_json_as_a_clean_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "site.config.json"
            for raw in (b'{"DOMAIN": ', b"\xff\xfe not utf-8"):
                config_path.write_bytes(raw)
                with self.subTest(raw=raw), patch("build.CONFIG", str(config_path)):
                    with self.assertRaisesRegex(SystemExit, "site.config.json is not valid JSON"):
                        load_config()

    def test_configured_verification_proofs_are_published_outside_the_sitemap(self) -> None:
        sample = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))
        tokens = {"bing_msvalidate": "0A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D",
                  "google_html_file": "google0123456789abcdef.html",
                  "indexnow_key": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"}
        with tempfile.TemporaryDirectory() as directory:
            repo = self.cli_repo(directory, json.dumps(dict(sample, verification=tokens)))
            for script in ("build.py", "quality_check.py", "check_artifacts.py"):
                with self.subTest(script=script):
                    result = self.run_cli(repo, script)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            site = repo / "site"
            self.assertEqual((site / "google0123456789abcdef.html").read_bytes(),
                             b"google-site-verification: google0123456789abcdef.html")
            self.assertEqual((site / "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d.txt").read_bytes(),
                             b"a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")
            index = (site / "index.html").read_text(encoding="utf-8")
            self.assertEqual(index.count('<meta name="msvalidate.01" content="0A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D">'), 1)
            sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
            self.assertNotIn("google0123456789abcdef", sitemap)
            self.assertNotIn("a1b2c3d4-e5f6", sitemap)
            manifest = json.loads((site / "content-manifest.json").read_text(encoding="utf-8"))
            self.assertIn("google0123456789abcdef.html", [row["path"] for row in manifest["files"]])

    def test_empty_verification_tokens_publish_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            template.mkdir()
            (template / "index.html").write_text("<head>\n{{VERIFICATION_META}}\n</head>\n", encoding="utf-8")
            build_site_staged(str(template), str(root / "site"), self.config())
            baseline = sorted(path.name for path in (root / "site").rglob("*"))
            self.assertFalse([name for name in baseline if name.startswith("google")])
            for verification in ({}, {"bing_msvalidate": "", "google_html_file": "", "indexnow_key": ""}):
                with self.subTest(verification=verification):
                    build_site_staged(str(template), str(root / "site"), dict(self.config(), verification=verification))
                    self.assertEqual(sorted(path.name for path in (root / "site").rglob("*")), baseline)
                    self.assertEqual((root / "site" / "index.html").read_text(encoding="utf-8"), "<head>\n\n</head>\n")

    def test_invalid_verification_tokens_are_refused(self) -> None:
        invalid = [
            {"google_html_file": "../x.html"},
            {"google_html_file": "google12345678.html.txt"},
            {"google_html_file": "googleXYZ12345.html"},
            {"google_html_file": "index.html"},
            {"bing_msvalidate": "short"},
            {"bing_msvalidate": '"><script>'},
            {"indexnow_key": "../../outside"},
            {"indexnow_key": 12345678},
        ]
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "site.config.json"
            for verification in invalid + ["not an object"]:
                with self.subTest(verification=verification):
                    config_path.write_text(json.dumps(dict(self.config(), verification=verification)), encoding="utf-8")
                    with patch("build.CONFIG", str(config_path)):
                        with self.assertRaisesRegex(SystemExit, "verification"):
                            load_config()
            template = Path(directory) / "template"
            template.mkdir()
            (template / "index.html").write_text("<h1>{{FULL_NAME}}</h1>\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "verification.google_html_file"):
                build_site_staged(str(template), str(Path(directory) / "site"),
                                  dict(self.config(), verification={"google_html_file": "../x.html"}))
            self.assertFalse((Path(directory) / "x.html").exists())

    def test_git_redirect_does_not_match_neighboring_dot_paths(self) -> None:
        # The comment says the rule is anchored so it cannot catch /.gitignore.
        # ^/\.git still matches every path that merely starts with /.git.
        rules = (ROOT / "template" / ".htaccess").read_text(encoding="utf-8")
        match = re.search(r"^RedirectMatch\s+404\s+(\S+)\s*$", rules, re.M)
        self.assertIsNotNone(match)
        pattern = re.compile(match.group(1))
        for path in ("/.git", "/.git/", "/.git/config", "/.git/HEAD"):
            self.assertTrue(pattern.search(path), path)
        for path in ("/.gitignore", "/.github", "/.github/workflows/quality-check.yml", "/llms.txt"):
            self.assertFalse(pattern.search(path), path)


if __name__ == "__main__":
    unittest.main()
