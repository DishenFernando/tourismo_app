"""Offline regression tests for Phase 9B navbar fix generator."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('navfix',HERE/'generate_navbar_fix.py')
fix=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)
ORIGINAL=Path(__file__).resolve().parents[1]/'tourismo_phase9b_nav_release/assets/NavigationPolish.css'
# The bootstrap installer copies only these two scripts to the user's repo,
# so tests use the installed existing CSS after Phase 9B.

class NavTests(unittest.TestCase):
    def fixture(self,crlf):
        d=tempfile.TemporaryDirectory()
        root=Path(d.name)/'repo';root.mkdir()
        p=root/fix.TARGET;p.parent.mkdir(parents=True)
        src='''/* Tourismo test header */\n.tourismo-navbar-shell { width:100%; }\n'''+fix.OLD+'''  .tourismo-navbar-shell [aria-haspopup="menu"] { min-width: 0; }\n}\n'''
        p.write_bytes(src.replace('\n','\r\n').encode('utf-8') if crlf else src.encode('utf-8'))
        subprocess.run(['git','init','-q'],cwd=root,check=True)
        subprocess.run(['git','add','.'],cwd=root,check=True)
        return d,root,p

    def test_git_patch_applies_to_lf_and_crlf(self):
        for crlf in (False,True):
            with self.subTest(crlf=crlf):
                d,root,path=self.fixture(crlf)
                try:
                    content=fix.patch_for(root)
                    out=Path(d.name)/'fix.patch';out.write_bytes(content.encode('utf-8'))
                    for extra in (['--check'],[]):
                        subprocess.run(['git','-c','core.whitespace=cr-at-eol','apply',*extra,str(out)],cwd=root,check=True)
                    data=path.read_bytes()
                    self.assertNotIn(b'overflow-x: auto',data)
                    self.assertIn(b'flex-wrap: wrap',data)
                    self.assertIn(b'overflow: visible',data)
                    self.assertEqual(data.count(b'\n'),data.count(b'\r\n') if crlf else data.count(b'\n'))
                    with self.assertRaises(fix.CompatibilityError):fix.patch_for(root)
                finally:
                    d.cleanup()

    def test_refuses_custom_nav_without_writing(self):
        d,root,path=self.fixture(False)
        try:
            before=path.read_bytes();path.write_bytes(before.replace(b'overflow-x: auto;',b'overflow-x: clip;'))
            edited=path.read_bytes()
            with self.assertRaises(fix.CompatibilityError):fix.patch_for(root)
            self.assertEqual(path.read_bytes(),edited)
        finally:d.cleanup()

if __name__=='__main__':unittest.main(verbosity=2)
