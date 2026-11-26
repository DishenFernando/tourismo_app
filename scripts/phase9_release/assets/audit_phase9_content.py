#!/usr/bin/env python3
"""Validate editorial translation handoff JSONL before any manual CMS import.

This is a local QA utility, NOT a publishing endpoint. No content is changed.
Usage: py -3 scripts/audit-phase9-content.py path/to/export.jsonl
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

VALID_TYPES = {'destination', 'attraction', 'guide'}
VALID_STATES = {'missing', 'draft', 'reviewed'}
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


def validate_record(record, seen):
    issues = []
    kind, slug = record.get('type'), record.get('slug')
    if kind not in VALID_TYPES:
        issues.append('type must be destination, attraction or guide')
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        issues.append('slug must be lowercase ASCII letters, digits and hyphens')
    key = (kind, slug)
    if key in seen:
        issues.append('duplicate type and slug')
    seen.add(key)

    source_url = record.get('source_url')
    if not isinstance(source_url, str) or not source_url.startswith('https://') or not urlparse(source_url).netloc:
        issues.append('source_url must be an HTTPS source reference')
    en = record.get('en')
    if not isinstance(en, dict) or not all(isinstance(en.get(k), str) and en[k].strip() for k in ('title', 'summary')):
        issues.append('en requires nonblank title and summary')
    counts = {'si_reviewed': 0, 'ta_reviewed': 0, 'si_pending': 0, 'ta_pending': 0}
    for code in ('si', 'ta'):
        item = record.get(code, {'status': 'missing'})
        if not isinstance(item, dict) or item.get('status') not in VALID_STATES:
            issues.append(f'{code} must have status missing, draft or reviewed')
            continue
        status = item['status']
        if status == 'missing':
            continue
        if not all(isinstance(item.get(k), str) and item[k].strip() for k in ('title', 'summary', 'translated_by')):
            issues.append(f'{code} {status} requires title, summary and translated_by')
        if status == 'reviewed':
            reviewer = item.get('reviewed_by')
            when = item.get('reviewed_at')
            if not isinstance(reviewer, str) or not reviewer.strip():
                issues.append(f'{code} reviewed requires reviewed_by')
            elif reviewer.strip().casefold() == str(item.get('translated_by', '')).strip().casefold():
                issues.append(f'{code} translator and reviewer must be different')
            try:
                parsed = date.fromisoformat(str(when))
                if parsed > date.today():
                    issues.append(f'{code} reviewed_at cannot be in the future')
            except ValueError:
                issues.append(f'{code} reviewed_at must be ISO YYYY-MM-DD')
            counts[f'{code}_reviewed'] += 1
        else:
            counts[f'{code}_pending'] += 1
    return issues, counts


def audit(path):
    errors, counts = [], {'records': 0, 'si_reviewed': 0, 'ta_reviewed': 0, 'si_pending': 0, 'ta_pending': 0}
    seen = set()
    with path.open(encoding='utf-8-sig') as handle:
        for number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f'Line {number}: invalid JSON: {exc.msg}')
                continue
            if not isinstance(record, dict):
                errors.append(f'Line {number}: expected a JSON object')
                continue
            counts['records'] += 1
            issues, row_counts = validate_record(record, seen)
            errors.extend(f'Line {number}: {error}' for error in issues)
            for key, value in row_counts.items():
                counts[key] += value
    if counts['records'] == 0:
        errors.append('File contains no editorial records')
    return {'counts': counts, 'errors': errors, 'ready_for_manual_review': not errors}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('file', type=Path, help='Native-editor handoff in JSONL format')
    args = cli.parse_args()
    if not args.file.is_file():
        cli.error(f'File not found: {args.file}')
    result = audit(args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ready_for_manual_review'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
