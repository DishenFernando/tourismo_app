#!/usr/bin/env python3
"""Tourismo Phase 8 rebaser for repositories already upgraded to Phase 7.1.

Read-only regarding the Tourismo repository. It takes the original Phase 8 Git patch,
transplants its hunks onto the *current* Phase 7.1 sources (strict context checks),
renumbers the Alembic revision to 0018, and emits a new changes-only Git patch.

No dependencies outside Python 3.9+ and Git.
"""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path
import re
import subprocess
import sys

REV_OLD = '0017_service_enquiries'
REV_NEW = '0018_service_enquiries'
PHASE71_REV = '0017_review_media'

ALLOWED = {
    'README.md',
    'apps/api/migrations/versions/0017_service_enquiries.py',
    'apps/api/tests/test_phase8_enquiries.py',
    'apps/api/tourismo/core/models.py',
    'apps/api/tourismo/enquiries/__init__.py',
    'apps/api/tourismo/enquiries/routes.py',
    'apps/api/tourismo/main.py',
    'apps/web/src/app/App.tsx',
    'apps/web/src/components/Header.tsx',
    'apps/web/src/features/Enquiries.tsx',
    'apps/web/src/features/EnquiryCompose.tsx',
    'apps/web/src/features/EnquiryReportModeration.tsx',
    'apps/web/src/features/ServiceListings.tsx',
    'apps/web/src/lib/api.ts',
    'docs/PHASE8_START_HERE.md',
    'docs/PHASE8_TOURIST_VENDOR_ENQUIRIES.md',
    'scripts/verify-phase8.ps1',
}


class UnsafeRebase(RuntimeError):
    pass


def after71_checks(root: Path) -> None:
    if not (root / '.git').exists():
        raise UnsafeRebase('The provided root is not a Git checkout. Use D:\\Tourismo\\Tourismo.')
    migration = root / 'apps/api/migrations/versions/0017_review_media_autopublish.py'
    if not migration.is_file():
        raise UnsafeRebase('Phase 7.1 migration is missing. Apply and verify Phase 7.1 first.')
    source = migration.read_text(encoding='utf-8')
    if not re.search(r"(?m)^revision\s*=\s*['\"]0017_review_media['\"]", source):
        raise UnsafeRebase('Unexpected Phase 7.1 revision identifier. Stop.')
    if not re.search(r"(?m)^down_revision\s*=\s*['\"]0016_customer_reviews['\"]", source):
        raise UnsafeRebase('Unexpected Phase 7.1 migration ancestry. Stop.')
    if not (root / 'apps/api/tourismo/reviews/safety.py').is_file():
        raise UnsafeRebase('Phase 7.1 review moderation source is missing. Stop.')
    if (root / 'apps/api/migrations/versions/0017_service_enquiries.py').exists():
        raise UnsafeRebase('Old Phase 8 migration already exists: do not mix migration heads.')
    if (root / 'apps/api/migrations/versions/0018_service_enquiries.py').exists():
        raise UnsafeRebase('New Phase 8 migration already exists: do not apply the same release twice.')


def parse_patch(source: str):
    """Return list of (file path, is new file, list of (old,new,start) hunks)."""
    sections = re.split(r'(?=^diff --git a/)', source, flags=re.MULTILINE)
    out = []
    for sec in sections:
        if not sec.strip():
            continue
        header = re.match(r'^diff --git a/(\S+) b/(\S+)\s*$', sec.splitlines()[0])
        if not header:
            raise UnsafeRebase('Unsupported patch structure. Stop.')
        path_a, path_b = header.groups()
        if path_a != path_b:
            raise UnsafeRebase(f'Renames are not supported: {path_a} -> {path_b}')
        if path_a not in ALLOWED:
            raise UnsafeRebase(f'Unexpected file in Phase 8 patch: {path_a}')
        new_file = bool(re.search(r'(?m)^new file mode ', sec))
        hunks = []
        lines = sec.splitlines(keepends=True)
        i = 0
        while i < len(lines):
            h = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', lines[i])
            if not h:
                i += 1
                continue
            start = int(h.group(1))
            i += 1
            old, new = [], []
            while i < len(lines) and not lines[i].startswith('@@ '):
                line = lines[i]
                if line.startswith('\\ No newline at end of file'):
                    raise UnsafeRebase(f'Non-newline marker is not supported safely for {path_a}')
                if not line or line[0] not in ' +-':
                    raise UnsafeRebase(f'Unexpected patch data in hunk: {path_a}: {line[:90]!r}')
                content = line[1:]
                if line[0] in (' ', '-'):
                    old.append(content)
                if line[0] in (' ', '+'):
                    new.append(content)
                i += 1
            hunks.append((start, old, new))
        if not hunks:
            raise UnsafeRebase(f'No hunks found in {path_a}')
        out.append((path_a, new_file, hunks))
    if not (15 <= len(out) <= 25):
        raise UnsafeRebase(f'Unexpected Phase 8 file count ({len(out)}); expected 17.')
    if not any(p == 'apps/api/migrations/versions/0017_service_enquiries.py' for p, _, _ in out):
        raise UnsafeRebase('Original Phase 8 migration not found in patch.')
    if len({p for p, _, _ in out}) != len(out):
        raise UnsafeRebase('Duplicate paths in patch.')
    return out


def strip_eol(s: str) -> str:
    return s.rstrip('\r\n')


def convert_new_content(path: str, content: str) -> str:
    # Only additions are transformed, NEVER original context. The old patch's
    # original context remains a strict applicability check.
    content = content.replace(REV_OLD, REV_NEW)
    if path == 'apps/api/migrations/versions/0017_service_enquiries.py':
        content = content.replace('Revises: 0016_customer_reviews', 'Revises: 0017_review_media')
        content = content.replace("down_revision = '0016_customer_reviews'", "down_revision = '0017_review_media'")
    elif path in {'docs/PHASE8_START_HERE.md', 'docs/PHASE8_TOURIST_VENDOR_ENQUIRIES.md'}:
        content = content.replace('`0016_customer_reviews`', '`0017_review_media`')
        content = content.replace('Phase 7 installed', 'Phase 7.1 installed')
        content = content.replace('Phase 7 source', 'Phase 7.1 source')
        content = content.replace('Phase 7 already deployed', 'Phase 7.1 already deployed')
        content = content.replace('Phase 7 live deployment', 'Phase 7.1 live deployment')
    elif path == 'README.md':
        content = content.replace('Phase 7 live deployment', 'Phase 7.1 live deployment')
    elif path == 'scripts/verify-phase8.ps1':
        content = re.sub(r'\$([A-Za-z_]\w*):(?=[ \t]|\$|\")', r'${\1}:', content)
    return content


def apply_hunks(path: str, local_content: str, hunks) -> str:
    sep = '\r\n' if '\r\n' in local_content else '\n'
    current = local_content.splitlines(keepends=True)
    shift = 0
    last_end = 0
    for hunk_no, (old_start, old, new) in enumerate(hunks, 1):
        needle = [strip_eol(s) for s in old]
        hay = [strip_eol(s) for s in current]
        if not needle:
            raise UnsafeRebase(f'{path}: insertion-only hunk has no safe context')
        matches = [idx for idx in range(last_end, len(hay) - len(needle) + 1)
                   if hay[idx:idx + len(needle)] == needle]
        if not matches:
            raise UnsafeRebase(f'{path}: hunk {hunk_no} context changed. No repository files were modified. '
                               'Share this failure rather than trying git apply --reject or --3way blindly.')
        if len(matches) > 1:
            expected = old_start - 1 + shift
            best_dist = min(abs(x - expected) for x in matches)
            closest = [x for x in matches if abs(x - expected) == best_dist]
            if len(closest) != 1:
                raise UnsafeRebase(f'{path}: ambiguous hunk {hunk_no}; refusing an uncertain edit')
            index = closest[0]
        else:
            index = matches[0]
        replacement = [strip_eol(line) + sep for line in new]
        # All files shipped in this source release have terminated lines.
        replacement = [convert_new_content(path, item) for item in replacement]
        current[index:index + len(old)] = replacement
        shift += len(new) - len(old)
        last_end = index + len(replacement)
    return ''.join(current)


def rebased_files(root: Path, sections):
    for old_path, new_file, hunks in sections:
        dest_path = old_path.replace(REV_OLD + '.py', REV_NEW + '.py')
        dest = root / dest_path
        if new_file:
            if dest.exists():
                raise UnsafeRebase(f'New Phase 8 file unexpectedly exists: {dest_path}')
            if len(hunks) != 1 or hunks[0][1]:
                raise UnsafeRebase(f'Invalid new-file hunk: {old_path}')
            target = ''.join(convert_new_content(old_path, s) for s in hunks[0][2])
            original = ''
        else:
            if not dest.is_file():
                raise UnsafeRebase(f'Existing source file is missing: {dest_path}')
            original = dest.read_bytes().decode('utf-8')
            target = apply_hunks(old_path, original, hunks)
        if original == target:
            raise UnsafeRebase(f'No modification produced for {dest_path}')
        yield dest_path, original, target, new_file


def make_diff(path: str, old: str, new: str, new_file: bool) -> str:
    # diff_lines use each input's real EOL. Git apply validates the resulting
    # patch against the original files before anything is installed.
    header = f'diff --git a/{path} b/{path}\n'
    if new_file:
        header += 'new file mode 100644\n'
    diff = ''.join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile='/dev/null' if new_file else f'a/{path}',
        tofile=f'b/{path}', lineterm='\n', n=3))
    if not diff.startswith('--- '):
        raise UnsafeRebase(f'Unable to generate safe diff for {path}')
    return header + diff


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Tourismo Git checkout root')
    parser.add_argument('--source', type=Path, required=True, help='Original Phase 8 Changes_Only.patch')
    parser.add_argument('--output', type=Path, required=True, help='New Phase 8 patch path')
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        after71_checks(root)
        if not args.source.is_file():
            raise UnsafeRebase(f'Original Phase 8 patch not found: {args.source}')
        if args.output.resolve() == args.source.resolve():
            raise UnsafeRebase('Refusing to overwrite the original Phase 8 patch.')
        original_patch = args.source.read_bytes().decode('utf-8-sig')
        sections = parse_patch(original_patch)
        rebased = list(rebased_files(root, sections))
        content = ''.join(make_diff(*record) for record in rebased)
        if 'down_revision = \'0017_review_media\'' not in content:
            raise UnsafeRebase('New migration ancestry check failed.')
        if '0018_service_enquiries' not in content:
            raise UnsafeRebase('New revision check failed.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(content.encode('utf-8'))
        print(f'Generated {len(rebased)}-file Phase 8 changes-only patch: {args.output}')
        print('Source repository has NOT been modified.')
        completed = subprocess.run(['git', 'apply', '--check', str(args.output.resolve())],
                                   cwd=root, capture_output=True, text=True)
        if completed.returncode:
            raise UnsafeRebase('git apply --check FAILED; do not apply.\n' +
                               (completed.stderr or completed.stdout).strip())
        print('PASS: git apply --check')
        print('NEXT: Back up PostgreSQL, then run git apply <generated-patch>.')
        print('After Docker rebuild, expected Alembic revision: 0018_service_enquiries')
        return 0
    except (UnsafeRebase, UnicodeDecodeError, OSError) as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
