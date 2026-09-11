"""Author and reader workflow regressions using synthetic content."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from article import create_article


class WorkflowTests(unittest.TestCase):
    def test_new_article_accepts_only_valid_explicit_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'template').mkdir()
            target = create_article(root, 'dated', 'Dated', published='2026-01-01', updated='2026-02-01')
            text = target.read_text(encoding='utf-8')
            self.assertIn('published: 2026-01-01', text)
            self.assertIn('updated: 2026-02-01', text)
            self.assertIn('status: draft', text)
            for options in ({'published': '2026-02-30'}, {'updated': 'tomorrow'},
                            {'published': '2026-02-02', 'updated': '2026-02-01'}):
                with self.assertRaises(ValueError):
                    create_article(root, 'invalid', 'Invalid', **options)
            self.assertFalse((root / 'template/writing/invalid.md').exists())

    def test_import_body_preserves_source_and_stays_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'template').mkdir()
            source = root / 'notes.md'
            source.write_text('# Imported\n\nCafé notes.\n', encoding='utf-8')
            target = create_article(root, 'notes', 'Notes', body_path=source)
            self.assertIn('status: draft', target.read_text(encoding='utf-8'))
            self.assertTrue(target.read_text(encoding='utf-8').endswith(source.read_text(encoding='utf-8')))
            with self.assertRaises(FileExistsError):
                create_article(root, 'notes', 'Notes', body_path=source)
            source.write_text('<!--\nstatus: published\n-->\n# Unsafe metadata', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'metadata'):
                create_article(root, 'other', 'Other', body_path=source)
            self.assertFalse((root / 'template/writing/other.md').exists())


if __name__ == '__main__':
    unittest.main()
