#!/usr/bin/env python3
"""Read-only search for Tourismo editorial load failures.

Run from repository root. Prints source locations of user-visible errors and
relevant API calls, never requests or changes data. After finding the call,
use the browser Network tab to inspect the failed request and its HTTP status.
"""
from pathlib import Path
import argparse
import re

TERMS = ("Some editorial content could not be loaded", "content language", "fallback_used")
KEYWORDS = re.compile(r'fetch\(|Promise\.all|/api/v1/|get[A-Z]\w*\(', re.I)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    args=parser.parse_args()
    src=args.root/'apps/web/src'
    if not src.is_dir():
        parser.error(f'Frontend folder not found: {src}')
    match_count=0
    for path in sorted(src.rglob('*')):
        if path.suffix not in ('.ts','.tsx'): continue
        try: lines=path.read_text(encoding='utf-8-sig').splitlines()
        except UnicodeError: continue
        hits=[i for i,line in enumerate(lines) if any(term.lower() in line.lower() for term in TERMS)]
        for i in hits:
            match_count+=1
            print(f'\n{path.relative_to(args.root)}:{i+1}: {lines[i].strip()[:220]}')
            for j in range(max(0,i-30),min(len(lines),i+31)):
                if j!=i and KEYWORDS.search(lines[j]):
                    print(f'    {j+1}: {lines[j].strip()[:190]}')
    if not match_count: print('No exact banner reference found. Search the browser Network tab for failed content requests.')
    print('\nBrowser check: DevTools > Network > Fetch/XHR > reload the destination page > inspect failed URL/status/body.')
    print('A missing or unreviewed translation and an HTTP/API failure are different problems. Do not suppress errors or fabricate content.')
    return 0

if __name__=='__main__': raise SystemExit(main())
