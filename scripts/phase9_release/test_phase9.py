#!/usr/bin/env python3
"""Self-test for Phase 9A patch export. Requires Git + Python 3.9+."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('phase9_generator', HERE / 'generate_phase9_patch.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def build_fake(root):
    files = {
        'apps/api/migrations/versions/0018_service_enquiries.py': "revision = '0018_service_enquiries'\ndown_revision = '0017_review_media'\n",
        'apps/api/migrations/versions/0017_review_media_autopublish.py': 'revision = "0017_review_media"\n',
        'apps/api/tourismo/enquiries/routes.py': '# Phase 8\n',
        'apps/web/src/app/App.tsx': '''import {BrowserRouter, Routes, Route} from 'react-router-dom'
import {Enquiries} from '../features/Enquiries'
import {EnquiryReportModeration} from '../features/EnquiryReportModeration'
export default function App() {
  return <BrowserRouter><div className="min-h-screen bg-cream text-ink flex flex-col"><Header/>
    <div className="flex-1"><Routes>
      <Route path="/enquiries" element={<Enquiries/>}/>
      <Route path="*" element={<main>Not found</main>}/>
    </Routes></div><Footer/></div></BrowserRouter>
}
''',
        'apps/web/src/components/Header.tsx': '''import {Link} from 'react-router-dom'
const links = [{path:'/', name:'Home'}, {path:'/discover', name:'Discover'}]
export function Header() {
  return <nav>{links.map(link=><Link key={link.path} to={link.path}>{link.name}</Link>)}</nav>
}
''',
    }
    for path, content in files.items():
        dest = root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding='utf-8')
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)


class Phase9GeneratorTests(unittest.TestCase):
    def test_patch_applies_to_synthetic_phase8(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            build_fake(root)
            content, touched = g.build_patch(root)
            self.assertEqual(len(touched), 8)
            patch = Path(tmp) / 'feature.patch'
            # Binary output avoids Windows newline translation corrupting mixed-CRLF diffs.
            patch.write_bytes(content.encode('utf-8'))
            subprocess.run(['git', 'apply', '--check', str(patch)], cwd=root, check=True)
            subprocess.run(['git', 'apply', str(patch)], cwd=root, check=True)
            self.assertIn('LocaleProvider', (root / 'apps/web/src/app/App.tsx').read_text())
            self.assertIn('navLabel', (root / 'apps/web/src/components/Header.tsx').read_text())
            self.assertTrue((root / 'apps/web/src/features/SiteChrome.tsx').is_file())
            with self.assertRaises(g.IncompatibleSource):
                g.build_patch(root)

    def test_routes_wrapper_accepts_formatted_layouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_fake(root)
            base = (root / 'apps/web/src/app/App.tsx').read_text(encoding='utf-8')
            original = '    <div className="flex-1"><Routes>'
            self.assertIn(original, base)
            variants = [
                '    <div className="flex-1">\n      <Routes>',
                '    <main className="flex-1"><Routes>',
                '    <div className="flex-1 min-h-0">\n      <Routes>',
            ]
            for variant in variants:
                with self.subTest(variant=variant):
                    updated = g.update_app(base.replace(original, variant))
                    self.assertIn('<div id="tourismo-content" tabIndex={-1}><Routes>', updated)
                    self.assertEqual(updated.count('id="tourismo-content"'), 1)
                    self.assertEqual(updated.count('<LocaleProvider>'), 1)
                    self.assertEqual(updated.count('</LocaleProvider>'), 1)

    def test_patch_applies_to_windows_crlf_sources(self):
        """The diff must remain Git-applicable with Windows CRLF source files.

        Python's default text writes translate newlines on Windows, which can
        double carriage returns in already-CRLF diff lines. Always write the
        patch bytes exactly as the generator produced them.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            build_fake(root)
            for relative in ('apps/web/src/app/App.tsx',
                             'apps/web/src/components/Header.tsx'):
                path = root / relative
                raw = path.read_bytes().replace(b'\r\n', b'\n')
                path.write_bytes(raw.replace(b'\n', b'\r\n'))
            content, touched = g.build_patch(root)
            self.assertEqual(len(touched), 8)
            patch = Path(tmp) / 'phase9-windows.patch'
            patch.write_bytes(content.encode('utf-8'))
            # CR is an expected end-of-line byte in this Windows fixture.
            subprocess.run(['git', '-c', 'core.whitespace=cr-at-eol', 'apply', '--check', str(patch)],
                           cwd=root, check=True)
            subprocess.run(['git', '-c', 'core.whitespace=cr-at-eol', 'apply', str(patch)],
                           cwd=root, check=True)
            self.assertIn('LocaleProvider',
                          (root / 'apps/web/src/app/App.tsx').read_text(encoding='utf-8'))
            self.assertIn('navLabel',
                          (root / 'apps/web/src/components/Header.tsx').read_text(encoding='utf-8'))

    def test_rejects_incorrect_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_fake(root)
            (root / 'apps/api/migrations/versions/0018_service_enquiries.py').write_text("revision = '0018_wrong'\n")
            with self.assertRaises(g.IncompatibleSource):
                g.build_patch(root)

    def test_editorial_validator_does_not_publish(self):
        source = (HERE / 'assets/audit_phase9_content.py').read_text(encoding='utf-8')
        self.assertIn('ready_for_manual_review', source)
        self.assertNotIn('INSERT INTO', source)
        self.assertNotIn('UPDATE service_listings', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
