#!/usr/bin/env python3
"""Audit/repair known UTF-8 decoded-as-Windows-1252 mojibake in Tourismo text.

Uses only Python's standard library. Never touches the database, .env, or Docker.
Run --check first, then --fix to make backups and repair recognized sequences.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Punctuation actually used by Tourismo and script-specific Sinhala / Tamil ranges.
# Restrict replacements to full, known-encodable mojibake sequences so normal text is unchanged.
COMMON_POINTS = (
    0x00A0, 0x00B0, 0x00B7, 0x00D7, 0x00A9, 0x00AE,
    0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D,
    0x2022, 0x2026, 0x2039, 0x203A, 0x20AC,
    0x2190, 0x2192, 0x2248, 0x2713, 0x2714, 0x2715, 0x2717,
)
SUSPECT = re.compile(r"(?:Â[·°©®\xa0]|â[€†œ„•]|à[¶®]|ðŸ|\ufffd)")
ALLOWED_EXTENSIONS = frozenset({'.ts', '.tsx', '.css', '.js', '.mjs', '.py', '.html'})


def misplaced(text: str) -> str | None:
    """Reverse one UTF-8 -> Windows-1252 accidental decode, if fully reversible."""
    try:
        corrupted = text.encode('utf-8').decode('cp1252', errors='strict')
    except UnicodeError:
        return None
    return corrupted if corrupted != text else None


def replacements() -> tuple[tuple[str, str], ...]:
    points = COMMON_POINTS + tuple(range(0x0B80, 0x0C00)) + tuple(range(0x0D80, 0x0E00))
    pairs: dict[str, str] = {}
    for point in points:
        char = chr(point)
        once = misplaced(char)
        if once is None or len(once) < 2:
            continue
        pairs[once] = char
        twice = misplaced(once)
        if twice is not None:
            pairs[twice] = char
    # Longer patterns first to avoid replacing the tail of twice-corrupted text.
    return tuple(sorted(pairs.items(), key=lambda item: -len(item[0])))


REPLACEMENTS = replacements()


def repair(text: str) -> tuple[str, int]:
    result = text
    for _ in range(3):
        old = result
        for bad, good in REPLACEMENTS:
            result = result.replace(bad, good)
        if result == old:
            break
    return result, sum(text.count(bad) for bad, _ in REPLACEMENTS)


def source_paths(root: Path):
    areas = (root / 'apps/web/src', root / 'apps/api/tourismo')
    for area in areas:
        if area.is_dir():
            for file in sorted(area.rglob('*')):
                if file.is_file() and file.suffix in ALLOWED_EXTENSIONS:
                    yield file
    index = root / 'apps/web/index.html'
    if index.is_file():
        yield index


def audit(root: Path, do_fix: bool) -> int:
    files_checked = 0
    files_changed = 0
    known_hits = 0
    problems: list[str] = []
    for file in source_paths(root):
        files_checked += 1
        raw = file.read_bytes()
        try:
            text = raw.decode('utf-8', errors='strict')
        except UnicodeDecodeError as exc:
            problems.append(f'{file.relative_to(root)}: invalid UTF-8 at byte {exc.start}; no automatic conversion')
            continue
        repaired, hits = repair(text)
        known_hits += hits
        if repaired != text:
            if not do_fix:
                problems.append(f'{file.relative_to(root)}: recognized mojibake ({hits} matches)')
                continue
            backup = file.with_name(file.name + '.before-encoding-fix')
            if not backup.exists():
                backup.write_bytes(raw)
            file.write_bytes(repaired.encode('utf-8'))
            files_changed += 1
            print(f'FIXED {file.relative_to(root)} (original saved as {backup.name})')
        leftover = SUSPECT.search(repaired)
        if leftover:
            problems.append(f'{file.relative_to(root)}: suspicious characters remain near {leftover.group(0)!r}; review manually')
    index = root / 'apps/web/index.html'
    if index.is_file() and not re.search(r'<meta\s+charset=["\']?utf-8', index.read_text('utf-8'), flags=re.I):
        problems.append('apps/web/index.html: missing UTF-8 meta declaration')
    print(f'Checked {files_checked} files. Known broken sequences: {known_hits}. Files changed: {files_changed}.')
    if files_checked == 0:
        problems.append('Tourismo source directories not found. Run from the project root.')
    if problems:
        for issue in problems:
            print('CHECK:', issue, file=sys.stderr)
        return 1
    print('PASS: source files are valid UTF-8 and contain no recognized mojibake.')
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='Read-only source audit (nonzero on corruption)')
    mode.add_argument('--fix', action='store_true', help='Repair recognized sequences, preserving source backups')
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Tourismo project root')
    args = parser.parse_args(argv)
    return audit(args.root.resolve(), args.fix)


if __name__ == '__main__':
    sys.exit(main())
