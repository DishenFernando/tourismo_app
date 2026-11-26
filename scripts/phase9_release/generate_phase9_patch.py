#!/usr/bin/env python3
"""Export a defensive changes-only Phase 9A Git patch against the user's real checkout.

The program only READS the Tourismo source tree. It writes the exported patch to
--output, not application files. No git reset, stash, merges, DB changes or destructive ops.
"""
from __future__ import annotations

import argparse
import difflib
from pathlib import Path
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parent
ASSETS = BASE / 'assets'
NEW_FILES = {
    'apps/web/src/i18n/LocaleProvider.tsx': 'LocaleProvider.tsx',
    'apps/web/src/features/SiteChrome.tsx': 'SiteChrome.tsx',
    'apps/web/src/features/AccessibilityPage.tsx': 'AccessibilityPage.tsx',
    'scripts/audit-phase9-content.py': 'audit_phase9_content.py',
    'scripts/verify-phase9.ps1': 'verify-phase9.ps1',
    'docs/PHASE9_CONTENT_LOCALIZATION_ACCESSIBILITY.md': 'PHASE9_CONTENT_LOCALIZATION_ACCESSIBILITY.md',
}


class IncompatibleSource(RuntimeError):
    pass


def replace_once(text: str, before: str, after: str, path: str) -> str:
    n = text.count(before)
    if n != 1:
        raise IncompatibleSource(f'{path}: expected exactly one anchor {before[:95]!r}, found {n}. '
                                 'No application files changed. Share the failure to rebase safely.')
    return text.replace(before, after, 1)


def check_preconditions(root: Path) -> None:
    if not (root / '.git').exists():
        raise IncompatibleSource('Root is not a Git checkout; use D:\\Tourismo\\Tourismo')
    migration = root / 'apps/api/migrations/versions/0018_service_enquiries.py'
    if not migration.is_file():
        raise IncompatibleSource('Expected Phase 8 migration 0018_service_enquiries.py not found. '
                                 'Apply Phase 8 after Phase 7.1 first.')
    text = migration.read_text(encoding='utf-8-sig')
    for key, value in [('revision', '0018_service_enquiries'), ('down_revision', '0017_review_media')]:
        if not re.search(rf'(?m)^{key}\s*=\s*[\'\"]{value}[\'\"]', text):
            raise IncompatibleSource(f'Unexpected Phase 8 migration ancestry: expected {key}={value}')
    if not (root / 'apps/api/tourismo/enquiries/routes.py').is_file():
        raise IncompatibleSource('Phase 8 enquiry source missing; cannot safely continue.')
    if not (root / 'apps/api/migrations/versions/0017_review_media_autopublish.py').is_file():
        raise IncompatibleSource('Phase 7.1 review media migration missing.')
    for relative in NEW_FILES:
        if (root / relative).exists():
            raise IncompatibleSource(f'Phase 9A file already exists: {relative}. Refusing to overwrite.')


def update_app(text: str) -> str:
    path = 'apps/web/src/app/App.tsx'
    nl = '\r\n' if '\r\n' in text else '\n'
    if 'EnquiryReportModeration' not in text or 'Enquiries' not in text:
        raise IncompatibleSource(f'{path}: Phase 8 routes not detected.')
    imports = (
        "import {LocaleProvider} from '../i18n/LocaleProvider'" + nl +
        "import {SkipToContent, LocaleToolbar, RouteMetadata} from '../features/SiteChrome'" + nl +
        "import {AccessibilityPage} from '../features/AccessibilityPage'" + nl + nl
    )
    text = replace_once(text, 'export default function App() {', imports+'export default function App() {', path)
    text = replace_once(text,
        '<BrowserRouter><div className="min-h-screen bg-cream text-ink flex flex-col"><Header/>',
        '<BrowserRouter><LocaleProvider><div className="min-h-screen bg-cream text-ink flex flex-col"><SkipToContent/><Header/><LocaleToolbar/><RouteMetadata/>', path)
    # Do not assume the Route container uses one fixed JSX line or class name.
    # Wrap only the unique Routes tree so the skip-link always has a focus target.
    # This preserves the existing layout container, routes, and their state.
    text = replace_once(text, '<Routes>',
        '<div id="tourismo-content" tabIndex={-1}><Routes>', path)
    text = replace_once(text, '</Routes>', '</Routes></div>', path)
    text = replace_once(text, '      <Route path="*" element=',
        '      <Route path="/accessibility" element={<AccessibilityPage/>}/>' + nl + '      <Route path="*" element=', path)
    # Close LocaleProvider at BrowserRouter's boundary; do not depend on
    # footer/route-container whitespace or exact JSX formatting.
    text = replace_once(text, '</BrowserRouter>', '</LocaleProvider></BrowserRouter>', path)
    return text


def update_header(text: str) -> str:
    path = 'apps/web/src/components/Header.tsx'
    nl = '\r\n' if '\r\n' in text else '\n'
    text = replace_once(text, 'export function Header() {',
        'export function Header() {' + nl +
        '  const {locale} = useLocale()' + nl +
        '  const links = baseLinks.map(item => ({...item, name: navLabel(locale, item.path, item.name)}))', path)
    # Existing Header owns the nav list; translate its labels without changing route/access controls.
    text = replace_once(text, 'const links = [{path:', 'const baseLinks = [{path:', path)
    text = "import {useLocale, navLabel} from '../i18n/LocaleProvider'" + nl + text
    if "{link.name}" not in text and "{item.name}" not in text and "{l.name}" not in text:
        raise IncompatibleSource(f'{path}: no known nav label rendering reference; review locally before editing.')
    return text


def patch_section(path: str, before: str, after: str, is_new: bool) -> str:
    if before == after:
        raise IncompatibleSource(f'No changes produced for {path}')
    header = f'diff --git a/{path} b/{path}\n'
    if is_new:
        header += 'new file mode 100644\n'
    body = ''.join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile='/dev/null' if is_new else f'a/{path}', tofile=f'b/{path}',
        n=3, lineterm='\n'))
    if not body.startswith('--- '):
        raise IncompatibleSource(f'Cannot produce a diff for {path}')
    return header + body


def build_patch(root: Path) -> tuple[str, list[str]]:
    check_preconditions(root)
    pieces, touched = [], []
    for path, update in [
        ('apps/web/src/app/App.tsx', update_app),
        ('apps/web/src/components/Header.tsx', update_header),
    ]:
        old = (root / path).read_bytes().decode('utf-8-sig')
        new = update(old)
        pieces.append(patch_section(path, old, new, False))
        touched.append(path)
    for path, asset in NEW_FILES.items():
        content = (ASSETS / asset).read_text(encoding='utf-8')
        if not content.endswith('\n'):
            raise IncompatibleSource(f'Asset lacks final newline: {asset}')
        pieces.append(patch_section(path, '', content, True))
        touched.append(path)
    return ''.join(pieces), touched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Tourismo Git root')
    parser.add_argument('--output', type=Path, help='Export exact changes-only patch (required unless --check)')
    parser.add_argument('--check', action='store_true', help='Dry-run source anchor/compatibility checks')
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        content, touched = build_patch(root)
        print(f'Phase 9A source compatibility OK: {len(touched)} feature files')
        for file in touched:
            print(' -', file)
        if args.check:
            print('DRY-RUN ONLY: application source unchanged')
            return 0
        if not args.output:
            raise IncompatibleSource('Supply --output PATH to export a Git patch')
        output = args.output.resolve()
        if root == output or output.is_relative_to(root):
            raise IncompatibleSource('Export your patch outside the repository, e.g. the Downloads folder.')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding='utf-8', newline='')
        result = subprocess.run(['git', '-C', str(root), 'apply', '--check', str(output)], capture_output=True, text=True)
        if result.returncode != 0:
            output.unlink(missing_ok=True)
            raise IncompatibleSource('git apply --check rejected the generated patch:\n' + result.stderr.strip())
        print('PASS: git apply --check')
        print('Generated exact changes-only patch:', output)
        print('NEXT: git apply --check <patch> followed by git apply <patch>')
        return 0
    except (IncompatibleSource, OSError, UnicodeError) as exc:
        print('STOP:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
