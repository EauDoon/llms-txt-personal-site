"""Integrated editorial and reader contracts for the static publisher."""
import sys
import json
import shutil
import tempfile
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build import build_site_staged, json_block
from build_writing_html import md_to_html
from email_addresses import contact_values
from publishing import article_metadata
from article import create_article


class PublishingTests(unittest.TestCase):
    def test_article_cli_creates_inert_draft_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            repo = Path(directory)
            shutil.copytree(ROOT / 'scripts', repo / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            title = 'Notes [draft] </script> --> & {{EMAIL}}'
            command = [sys.executable, str(repo / 'scripts' / 'article.py'), 'new', 'field-notes', '--title', title,
                       '--description', 'A bounded summary.', '--topic', 'Research']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            path = template / 'writing' / 'field-notes.md'
            original = path.read_bytes()
            meta, _ = article_metadata(original.decode())
            self.assertEqual(meta['title'], title)
            self.assertEqual(meta['status'], 'draft')
            self.assertNotIn('published', meta)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(path.read_bytes(), original)
            build_site_staged(str(template), str(site), cfg)
            self.assertFalse((site / 'writing' / 'field-notes.md').exists())
            for slug in ('../escape', 'Uppercase', 'con', '/absolute', 'a--b'):
                with self.subTest(slug=slug), self.assertRaises(ValueError):
                    create_article(repo, slug, 'Title')
            with self.assertRaises(ValueError):
                create_article(repo, 'other', 'Title\nstatus: published')

    def fixture(self, directory):
        template, site = Path(directory) / 'template', Path(directory) / 'site'
        shutil.copytree(ROOT / 'template', template)
        cfg = json.loads((ROOT / 'site.config.example.json').read_text(encoding='utf-8'))
        return template, site, dict(cfg, **json_block(cfg))

    def test_draft_bytes_never_enter_public_build_and_transitions_remove_them(self):
        sentinel = 'UNPUBLISHED_SYNTHETIC_SENTINEL_63eaf7'
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            path = template / 'writing' / 'pending.md'
            source = '<!--\nstatus: %s\ntitle: Pending\n-->\n# Pending\n' + sentinel
            path.write_text(source % 'draft', encoding='utf-8')
            (template / 'writing' / 'pending.html').write_text(sentinel, encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            self.assertFalse((site / 'writing' / 'pending.md').exists())
            for output in site.rglob('*'):
                if output.is_file():
                    self.assertNotIn(sentinel.encode(), output.read_bytes(), str(output))
            path.write_text(source % 'published', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            self.assertIn(sentinel, (site / 'writing' / 'pending.html').read_text(encoding='utf-8'))
            path.write_text(source % 'draft', encoding='utf-8')
            build_site_staged(str(template), str(site), cfg)
            self.assertFalse((site / 'writing' / 'pending.html').exists())

    def test_ambiguous_article_status_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            template, site, cfg = self.fixture(directory)
            build_site_staged(str(template), str(site), cfg)
            original = (site / 'content-manifest.json').read_bytes()
            for metadata in ('status: Draft', 'status: draft\nSTATUS: published',
                             'statuz: draft', 'status:', 'status: {{STATUS}}', 'status draft'):
                with self.subTest(metadata=metadata):
                    (template / 'writing' / 'bad.md').write_text('<!--\n' + metadata + '\n-->\n# Bad', encoding='utf-8')
                    with self.assertRaises(ValueError):
                        build_site_staged(str(template), str(site), cfg)
                    self.assertEqual((site / 'content-manifest.json').read_bytes(), original)

    def test_paired_contact_framing_agrees_in_source_and_rendered_prose(self):
        address = "o'hara@yourname.com"
        for marker in ('', '**', '_', '`', '``', '**_'):
            for quote in ("'", '"'):
                source = marker + quote + 'mailto:o%27hara%40yourname.com' + quote + marker[::-1]
                for text, suffix in ((source, '.md'), (md_to_html(source), '.html')):
                    with self.subTest(source=source, suffix=suffix):
                        self.assertEqual(contact_values(text, suffix)[1], [address])

    def test_contact_destination_corruption_is_never_markdown_framing(self):
        for source in ("[Contact](mailto:a@x.example'evil)", "<mailto:a@x.example'evil>",
                       "**'mailto:a@x.example'**evil", "_'mailto:a@x.example'evil'_",
                       "`'mailto:a@x.example'evil'`", "mailto:a@x.example'**"):
            with self.subTest(source=source):
                values = contact_values(source, '.md')[1]
                self.assertTrue(values)
                self.assertNotIn('a@x.example', values)
        self.assertEqual(contact_values('<a href="mailto:a@x.example\'**">Contact</a>', '.html')[1],
                         ["a@x.example'**"])


if __name__ == '__main__':
    unittest.main()
