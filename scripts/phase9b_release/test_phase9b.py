#!/usr/bin/env python3
"""Reproducible no-network Phase 9B generator/UX fixture tests."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('phase9b_generator',HERE/'generate_phase9b_patch.py')
g=importlib.util.module_from_spec(sp)
sp.loader.exec_module(g)

class GeneratorTests(unittest.TestCase):
    def fixture(self,root,crlf=False):
        files={
            'apps/api/migrations/versions/0018_service_enquiries.py':"revision = '0018_service_enquiries'\ndown_revision = '0017_review_media'\n",
            'apps/web/src/i18n/LocaleProvider.tsx':'export const preview = true\n',
            'apps/web/src/features/AccessibilityPage.tsx':'export const AccessibilityPage=()=>null\n',
            'apps/web/src/features/SiteChrome.tsx':(HERE/'work/SiteChromePhase9A.tsx').read_text(encoding='utf-8'),
            'apps/web/src/components/Header.tsx':'''export function Header(){return <header><nav><a href="/">Home</a></nav><span className="old">EN ·<br/> SI/TA planned</span></header>}\n''',
            'apps/web/src/app/App.tsx':'''import {LocaleProvider} from '../i18n/LocaleProvider'
import {SkipToContent, LocaleToolbar} from '../features/SiteChrome'
import {AccessibilityPage} from '../features/AccessibilityPage'
export default function App() {
return <BrowserRouter><LocaleProvider><div><SkipToContent/><Header/><LocaleToolbar/>
<div><div id="tourismo-content"><Routes>
<Route path="/accessibility" element={<AccessibilityPage/>}/>
</Routes></div></div>
</div></LocaleProvider></BrowserRouter>
}
''',
        }
        for name,content in files.items():
            f=root/name;f.parent.mkdir(parents=True,exist_ok=True)
            f.write_bytes(content.replace('\n','\r\n').encode('utf-8') if crlf else content.encode('utf-8'))
        subprocess.run(['git','init','-q'],cwd=root,check=True)
        subprocess.run(['git','add','.'],cwd=root,check=True)

    def test_export_and_apply_phase9b(self):
        for crlf in (False,True):
            with self.subTest(crlf=crlf),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'repo';root.mkdir()
                self.fixture(root,crlf=crlf)
                data,paths,removed=g.build_patch(root)
                self.assertTrue(removed)
                self.assertEqual(len(paths),7)
                dest=Path(tmp)/'update.patch';dest.write_bytes(data.encode('utf-8'))
                subprocess.run(['git','-c','core.whitespace=cr-at-eol','apply','--check',str(dest)],cwd=root,check=True)
                subprocess.run(['git','-c','core.whitespace=cr-at-eol','apply',str(dest)],cwd=root,check=True)
                self.assertIn('tourismo-navbar-shell',(root/'apps/web/src/components/Header.tsx').read_text(encoding='utf-8'))
                self.assertNotIn('SI/TA planned',(root/'apps/web/src/components/Header.tsx').read_text(encoding='utf-8'))
                self.assertIn('Language coverage',(root/'apps/web/src/features/SiteChrome.tsx').read_text(encoding='utf-8'))
                with self.assertRaises(g.IncompatibleSource):g.build_patch(root)

    def test_admin_workbench_link_copies_role_guard(self):
        header = '''''''''export function Header(){ return <header className="sticky top-0">
  {auth.profile?.roles.some(r=>r==='admin'||r==='editor') && <Link role="menuitem" to="/admin" onClick={()=>setMenuOpen(false)} className="account-menu-item">Content dashboard</Link>}
</header> }
'''''''''
        updated, removed = g.update_header(header)
        self.assertFalse(removed)
        self.assertEqual(updated.count('to="/admin/translation-workbench"'), 1)
        self.assertEqual(updated.count('onClick={()=>setMenuOpen(false)}'), 2)
        self.assertIn('className="tourismo-navbar-shell sticky top-0"', updated)

    def test_incompatible_app_does_not_change_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            f=root/'apps/web/src/app/App.tsx';f.write_text('export default function App(){return null}',encoding='utf-8')
            old=f.read_bytes()
            with self.assertRaises(g.IncompatibleSource):g.build_patch(root)
            self.assertEqual(old,f.read_bytes())

    def test_compliant_header_preserves_account_menu(self):
        header='<header><button aria-haspopup="menu">Account</button><nav>Links</nav></header>'
        new,removed=g.update_header(header)
        self.assertFalse(removed)
        self.assertIn('className="tourismo-navbar-shell"',new)
        self.assertIn('aria-haspopup="menu"',new)

if __name__=='__main__':unittest.main(verbosity=2)
