#!/usr/bin/env python3
"""Read-only, source-aware Phase 9B-1 UI + translation QA patch generator.

Outputs a changes-only Git patch against the *actual* Tourismo checkout.
Does not modify App, Header, SiteChrome, DB, existing docs, or vendor code directly.
"""
from __future__ import annotations
import argparse
import difflib
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ASSETS = HERE / 'assets'
NEW_FILES = {
    'apps/web/src/features/NavigationPolish.css': 'NavigationPolish.css',
    'apps/web/src/features/TranslationWorkbench.tsx': 'TranslationWorkbench.tsx',
    'docs/PHASE9B_NAV_TRANSLATION_START.md': 'PHASE9B_NAV_TRANSLATION_START.md',
    'scripts/verify-phase9b.ps1': 'verify-phase9b.ps1',
}

class IncompatibleSource(RuntimeError): pass

def once(text: str, before: str, after: str, file: str) -> str:
    n = text.count(before)
    if n != 1:
        raise IncompatibleSource(f'{file}: expected exactly one {before!r}, found {n}. No files changed.')
    return text.replace(before, after, 1)

def check_preconditions(root: Path) -> None:
    if not (root/'.git').exists(): raise IncompatibleSource('Not a Git checkout')
    required = [
        'apps/api/migrations/versions/0018_service_enquiries.py',
        'apps/web/src/i18n/LocaleProvider.tsx',
        'apps/web/src/features/SiteChrome.tsx',
        'apps/web/src/features/AccessibilityPage.tsx',
        'apps/web/src/app/App.tsx',
        'apps/web/src/components/Header.tsx',
    ]
    for name in required:
        if not (root/name).is_file(): raise IncompatibleSource(f'Prerequisite missing: {name}')
    for name in NEW_FILES:
        if (root/name).exists(): raise IncompatibleSource(f'Phase 9B feature already exists: {name}')
    migration = (root/required[0]).read_text(encoding='utf-8-sig')
    if not re.search(r'''(?m)^revision\s*=\s*['"]0018_service_enquiries['"]''', migration):
        raise IncompatibleSource('Expected Phase 8 database migration source 0018_service_enquiries')

def update_app(text: str) -> str:
    path = 'apps/web/src/app/App.tsx'
    if "from '../features/SiteChrome'" not in text or '<LocaleProvider>' not in text:
        raise IncompatibleSource('Phase 9A components not installed in App.tsx')
    nl = '\r\n' if '\r\n' in text else '\n'
    text = once(text, 'export default function App() {',
        "import {TranslationWorkbench} from '../features/TranslationWorkbench'"+nl+nl+'export default function App() {', path)
    if len(re.findall(r'<Header\s*/>', text)) != 1:
        raise IncompatibleSource('Expected exactly one <Header/> in App.tsx')
    # Do not wrap Header: doing so can break an existing sticky header.
    target = '<Route path="/accessibility" element={<AccessibilityPage/>}/>'
    text = once(text, target, target+nl+'      <Route path="/admin/translation-workbench" element={<TranslationWorkbench/>}/>', path)
    return text

def update_sitechrome(text: str) -> str:
    path = 'apps/web/src/features/SiteChrome.tsx'
    if 'export function LocaleToolbar() {' not in text or 'const langHelp:' not in text:
        raise IncompatibleSource(f'{path}: expected Phase 9A LocaleToolbar and langHelp')
    nl = '\r\n' if '\r\n' in text else '\n'
    if 'NavigationPolish.css' in text: raise IncompatibleSource('NavigationPolish already wired')
    text = once(text, "import {useEffect, useState, type MouseEvent} from 'react'",
        "import './NavigationPolish.css'"+nl+"import {useEffect, useState, type MouseEvent} from 'react'", path)
    prefix, delim, old_toolbar = text.partition('export function LocaleToolbar() {')
    if not delim or 'return <section' not in old_toolbar:
        raise IncompatibleSource('Could not isolate LocaleToolbar safely')
    # Phase9A ends at this function. If another export follows, refuse and request rebase.
    if re.search(r'(?m)^export\s+(?:function|const|class)\s+', old_toolbar):
        raise IncompatibleSource('Unexpected exports after LocaleToolbar; do not overwrite them')
    toolbar = '''export function LocaleToolbar() {
  const {locale, setLocale} = useLocale()
  return <section aria-label="Language and accessibility tools" className="tourismo-utility-bar">
    <div className="wrap tourismo-utility-inner flex flex-wrap items-center justify-end gap-x-4 gap-y-2 py-2 text-sm">
      <label className="flex items-center gap-2 font-medium" htmlFor="tourismo-locale">
        <span>Language</span>
        <select id="tourismo-locale" aria-label="Interface navigation language" value={locale}
          onChange={event => setLocale(event.target.value as Locale)}
          className="min-h-11 rounded-lg border border-ink/30 bg-white px-3 py-2 text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pine">
          <option value="en" lang="en">English</option>
          <option value="si" lang="si">සිංහල (preview)</option>
          <option value="ta" lang="ta">தமிழ் (preview)</option>
        </select>
      </label>
      <Link to="/accessibility" className="inline-flex min-h-11 items-center rounded-lg px-2 underline underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pine">Accessibility</Link>
      <details className="text-ink/75">
        <summary className="inline-flex min-h-11 items-center px-2 underline underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pine">Language coverage</summary>
        <p lang={locale} className="tourismo-translation-note pb-2">{langHelp[locale]}</p>
      </details>
    </div>
  </section>
}
'''
    if nl != '\n': toolbar = toolbar.replace('\n', nl)
    return prefix+toolbar

# Only remove the obsolete, simple self-contained label. Preserve anything more complex.
OLD_LANGUAGE_STUB = re.compile(
    r'<(?P<tag>span|p|div)\b[^>]*>\s*EN\s*(?:·|•|&middot;)?\s*(?:<br\s*/?>)?\s*SI\s*/\s*TA\s*planned\s*</(?P=tag)>',
    flags=re.I|re.S,
)
def update_header(text: str) -> tuple[str, bool]:
    new, count = OLD_LANGUAGE_STUB.subn('', text)
    if count > 1: raise IncompatibleSource('More than one language teaser found in Header.tsx')
    # Add a CSS scope directly to the semantic header so sticky positioning,
    # mobile menus, account popovers and DOM hierarchy remain unchanged.
    tags = list(re.finditer(r'<header\b[^>]*>', new))
    if len(tags) != 1:
        raise IncompatibleSource('Expected exactly one semantic <header> in Header.tsx; refusing to guess')
    tag = tags[0].group()
    if 'tourismo-navbar-shell' in tag:
        raise IncompatibleSource('Phase 9B nav class already applied')
    if 'className="' in tag:
        replaced = tag.replace('className="', 'className="tourismo-navbar-shell ', 1)
    elif 'className=' in tag:
        raise IncompatibleSource('Header uses a nonliteral className; review required')
    else:
        replaced = tag.replace('<header', '<header className="tourismo-navbar-shell"', 1)
    new = new[:tags[0].start()]+replaced+new[tags[0].end():]
    # If a known role-guarded account-menu link exists, place the workbench
    # alongside Content dashboard. Copy its exact onClick and role guard.
    lines = new.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if 'role="menuitem" to="/admin"' in line and 'Content dashboard' in line:
            clone = line.replace('to="/admin"', 'to="/admin/translation-workbench"', 1).replace(
                'Content dashboard', 'Translation workbench', 1)
            lines.insert(i + 1, clone)
            break
    new = ''.join(lines)
    return new, bool(count)

def part(path: str, old: str, new: str, is_new: bool) -> str:
    if old == new: raise IncompatibleSource(f'No changes produced for {path}')
    diff = ''.join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile='/dev/null' if is_new else 'a/'+path, tofile='b/'+path, n=3, lineterm='\n'))
    if not diff.startswith('--- '): raise IncompatibleSource(f'Invalid patch for {path}')
    return f'diff --git a/{path} b/{path}\n' + ('new file mode 100644\n' if is_new else '') + diff

def build_patch(root: Path) -> tuple[str,list[str],bool]:
    check_preconditions(root)
    pieces=[]; touched=[]
    for name, update in [
        ('apps/web/src/app/App.tsx',update_app),
        ('apps/web/src/features/SiteChrome.tsx',update_sitechrome),
    ]:
        old=(root/name).read_bytes().decode('utf-8-sig')
        new=update(old)
        pieces.append(part(name,old,new,False));touched.append(name)
    name='apps/web/src/components/Header.tsx'
    old=(root/name).read_bytes().decode('utf-8-sig')
    new, removed=update_header(old)
    pieces.append(part(name,old,new,False));touched.append(name)
    for name,asset in NEW_FILES.items():
        content=(ASSETS/asset).read_text(encoding='utf-8')
        if not content.endswith('\n'):raise IncompatibleSource(f'Asset has no trailing newline: {asset}')
        pieces.append(part(name,'',content,True));touched.append(name)
    return ''.join(pieces),touched,removed

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    root=args.root.resolve()
    try:
        patch,touched,removed=build_patch(root)
        print('Phase 9B-1 source compatibility OK:',len(touched),'feature files')
        for name in touched:print(' -',name)
        if not removed:print('NOTE: Header language teaser was not a known safe-to-remove form. Review the preview label manually if still visible.')
        if args.check:
            print('DRY-RUN ONLY: no application files changed')
            return 0
        if not args.output:raise IncompatibleSource('Provide --output PATH for exported patch')
        output=args.output.resolve()
        if output == root or output.is_relative_to(root):raise IncompatibleSource('Export outside Git repository, e.g. Downloads')
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_bytes(patch.encode('utf-8'))  # Never translate CRLF lines on Windows.
        result=subprocess.run(['git','-c','core.whitespace=cr-at-eol','-C',str(root),'apply','--check',str(output)],capture_output=True,text=True)
        if result.returncode:
            output.unlink(missing_ok=True)
            raise IncompatibleSource('git apply --check rejected generated patch: '+result.stderr.strip())
        print('PASS: git apply --check')
        print('Generated changes-only Git patch:',output)
        return 0
    except (IncompatibleSource,OSError,UnicodeError) as exc:
        print('STOP:',exc,file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
