"""Author and reader workflow regressions using synthetic content."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from article import create_article


class WorkflowTests(unittest.TestCase):
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
