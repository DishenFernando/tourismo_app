#!/usr/bin/env python3
"""Generate a source-compatible, changes-only Tourismo Phase 9B navbar fix.

Only touches apps/web/src/features/NavigationPolish.css; preserves CRLF/LF.
Refuses to overwrite unknown customized navbar rules, or change the DB.
"""
from __future__ import annotations
import argparse
import difflib
from pathlib import Path
import subprocess
import sys

TARGET = 'apps/web/src/features/NavigationPolish.css'
OLD = '''/* Preserve single-line desktop links. On narrower desktop screens, navigation
   scrolls inside its own region instead of squeezing the profile/CTA or wrapping.
   Mobile navigation is still controlled by the existing Header component. */
@media (min-width: 1024px) {
  .tourismo-navbar-shell nav {
    flex-wrap: nowrap;
    column-gap: clamp(.45rem, .78vw, .95rem);
    overflow-x: auto;
    overflow-y: hidden;
    overscroll-behavior-inline: contain;
    scrollbar-width: thin;
    scroll-padding-inline: 12px;
  }
  .tourismo-navbar-shell nav a {
    white-space: nowrap;
    flex-shrink: 0;
    font-size: clamp(0.8125rem, 0.75vw + 0.18rem, 0.975rem);
    line-height: 1.4;
  }
'''
NEW = '''/* Desktop navigation: no inner scrollbar and no clipped links.
   If space becomes tight, wrap WHOLE links into a second row, rather than
   squeezing words or hiding primary routes. The original mobile menu remains
   responsible for viewports narrower than 1024px. */
@media (min-width: 1024px) {
  .tourismo-navbar-shell nav {
    display: flex;
    flex: 1 1 auto;
    min-width: 0;
    max-width: 100%;
    height: auto;
    align-items: center;
    align-content: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    column-gap: clamp(.35rem, .65vw, .75rem);
    row-gap: .2rem;
    overflow: visible;
  }
  .tourismo-navbar-shell nav a {
    white-space: nowrap;
    flex: 0 0 auto;
    font-size: clamp(0.8125rem, .56vw + .23rem, 0.92rem);
    line-height: 1.35;
  }
'''
class CompatibilityError(Exception):
    pass

def patch_for(root: Path) -> str:
    src = root / TARGET
    if not (root / '.git').exists():
        raise CompatibilityError('Not a Git repository root')
    if not src.is_file():
        raise CompatibilityError(f'Missing {TARGET} — Phase 9B nav polish may not be installed')
    raw = src.read_bytes()
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    text = raw[len(bom):].decode('utf-8')
    if '\r\n' in text and '\n' in text.replace('\r\n', ''):
        raise CompatibilityError('Mixed line endings detected; stop instead of normalizing other edits')
    nl = '\r\n' if '\r\n' in text else '\n'
    count = text.count(OLD.replace('\n', nl))
    if count != 1:
        if 'overflow-x: auto;' not in text and 'flex-wrap: wrap;' in text:
            raise CompatibilityError('Navbar scrollbar change appears already fixed')
        raise CompatibilityError(f'Expected the known Phase 9B nav rule once; found {count}. No changes made.')
    new_text = text.replace(OLD.replace('\n', nl), NEW.replace('\n', nl), 1)
    old = (bom.decode('utf-8') + text) if bom else text
    new = (bom.decode('utf-8') + new_text) if bom else new_text
    unified = ''.join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile='a/'+TARGET, tofile='b/'+TARGET, n=3, lineterm='\n'))
    if not unified.startswith('--- a/'):
        raise CompatibilityError('Patch generation failed')
    return f'diff --git a/{TARGET} b/{TARGET}\n' + unified

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--check',action='store_true')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    try:
        root=args.root.resolve()
        patch=patch_for(root)
        print('PASS: Phase 9B navbar source anchor found — only NavigationPolish.css will change')
        if args.check:
            print('DRY RUN: no application source changed')
            return 0
        if not args.output: raise CompatibilityError('Use --output outside the Git repository')
        out=args.output.resolve()
        if out.is_relative_to(root):
            raise CompatibilityError('Export the patch outside the repository (e.g. Downloads)')
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(patch.encode('utf-8'))
        result=subprocess.run(['git','-c','core.whitespace=cr-at-eol','-C',str(root),'apply','--check',str(out)],capture_output=True,text=True)
        if result.returncode:
            out.unlink(missing_ok=True)
            raise CompatibilityError('git apply --check failed: '+result.stderr.strip())
        print('PASS: git apply --check')
        print('Generated exact-source changes-only patch:',out)
        return 0
    except (CompatibilityError,OSError,UnicodeError) as exc:
        print('STOP:',exc,file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
