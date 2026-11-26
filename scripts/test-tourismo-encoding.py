#!/usr/bin/env python3
"""Stand-alone regression tests for the safe Tourismo Unicode repair utility."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

script = Path(__file__).with_name('repair-tourismo-text.py')
spec = importlib.util.spec_from_file_location('tourismo_encoding_repair', script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EncodingRegression(unittest.TestCase):
    def test_vendor_screen_examples(self):
        before = 'Accommodation Â· Draft | 1 Â· Business draft âœ“ | Continue â†’'
        after, count = module.repair(before)
        self.assertEqual(after, 'Accommodation · Draft | 1 · Business draft ✓ | Continue →')
        self.assertGreaterEqual(count, 3)

    def test_already_correct_text_is_unchanged(self):
        clean = 'Accommodation · Draft · ✓ → | සිංහල | தமிழ் | AI-generated illustration'
        self.assertEqual(module.repair(clean)[0], clean)

    def test_sinhala_and_tamil_repair(self):
        for word in ('සිංහල', 'தமிழ்'):
            broken = word.encode('utf-8').decode('cp1252', errors='replace')
            if '\ufffd' not in broken:
                self.assertEqual(module.repair(broken)[0], word)

    def test_idempotent(self):
        broken = '1 Â· Business draft âœ“'
        repaired = module.repair(broken)[0]
        self.assertEqual(module.repair(repaired)[0], repaired)

    def test_check_and_fix_preserves_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'apps/web/src/features'
            folder.mkdir(parents=True)
            (root / 'apps/web/index.html').write_text('<meta charset="UTF-8">', encoding='utf-8')
            file = folder / 'Vendors.tsx'
            file.write_text('const text = "Business Â· Draft âœ“";', encoding='utf-8')
            self.assertEqual(module.audit(root, False), 1)
            self.assertEqual(module.audit(root, True), 0)
            self.assertEqual(module.audit(root, False), 0)
            self.assertEqual(file.read_text(encoding='utf-8'), 'const text = "Business · Draft ✓";')
            self.assertTrue(file.with_name('Vendors.tsx.before-encoding-fix').exists())

    def test_invalid_utf8_never_changed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'apps/web/src'
            folder.mkdir(parents=True)
            file = folder / 'broken.ts'
            file.write_bytes(b'\xff')
            (root / 'apps/web/index.html').write_text('<meta charset="UTF-8">', encoding='utf-8')
            self.assertEqual(module.audit(root, True), 1)
            self.assertEqual(file.read_bytes(), b'\xff')


if __name__ == '__main__':
    unittest.main()
