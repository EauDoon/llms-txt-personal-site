from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

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

    def test_example_is_exact_rebuild_from_example_config(self) -> None:
        config = json.loads(
            (ROOT / "site.config.example.json").read_text(encoding="utf-8")
        )
        config = dict(config, **json_block(config))

        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "site"
            build_site(str(ROOT / "template"), str(generated), config)

            expected_files = {
                path.relative_to(ROOT / "example")
                for path in (ROOT / "example").rglob("*")
                if path.is_file()
            }
            generated_files = {
                path.relative_to(generated)
                for path in generated.rglob("*")
                if path.is_file()
            }
            differences = [
                "missing generated file: %s" % path.as_posix()
                for path in sorted(expected_files - generated_files)
            ]
            differences.extend(
                "unexpected generated file: %s" % path.as_posix()
                for path in sorted(generated_files - expected_files)
            )

            for path in sorted(expected_files & generated_files):
                expected = (ROOT / "example" / path).read_bytes()
                actual = (generated / path).read_bytes()
                if expected == actual:
                    continue
                first_changed = next(
                    (
                        offset
                        for offset, (left, right) in enumerate(zip(expected, actual))
                        if left != right
                    ),
                    min(len(expected), len(actual)),
                )
                differences.append(
                    "changed file: %s at byte %d (expected %r, generated %r)"
                    % (
                        path.as_posix(),
                        first_changed,
                        expected[first_changed : first_changed + 80],
                        actual[first_changed : first_changed + 80],
                    )
                )

            self.assertEqual(
                differences,
                [],
                "site.config.example.json rebuild differs from example/:\n"
                + "\n".join(differences),
            )

    def test_checked_in_example_has_no_reference_identity(self) -> None:
        markers = (
            b"straits" + b"x",
            b"xsgd",
            b"xusd",
            b"daniel" + b"oon",
            b"eau" + b"doon",
        )
        for directory in (ROOT / "template", ROOT / "example"):
            for path in directory.rglob("*"):
                if not path.is_file():
                    continue
                compact = re.sub(rb"[\s_-]+", b"", path.read_bytes().lower())
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertFalse(any(marker in compact for marker in markers))

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
            "EMAIL": "person@example.test",
            "JOB_TITLE": "Example Role",
            "EMPLOYER": "Example Employer",
            "EMPLOYER_URL": "https://employer.example.test",
            "LINKEDIN_SLUG": "example-person",
            "X_HANDLE": "exampleperson",
            "ABSENCE_EMPLOYMENT_DATES": "No employment dates are published.",
            "ABSENCE_RECORDED_MEDIA": "No recorded media was located",
            "ABSENCE_BYLINED_ARTICLE": "No bylined article was located.",
            "LAST_UPDATED": last_updated,
        }

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


if __name__ == "__main__":
    unittest.main()
