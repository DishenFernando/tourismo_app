#!/usr/bin/env python3
"""Tourismo Phase 10A: offline release/configuration readiness audit.

Read-only. Never displays environment values, credentials, URLs containing tokens,
or database connection strings. Does not contact outside services or change files.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

LATEST_MIGRATION = '0019_notifications_trust'


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str


def dotenv(path: Path) -> dict[str, str]:
    """Read plain dotenv values without expanding commands or secrets."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        match = re.match(r'^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)$', line)
        if not match:
            continue
        value = match.group(2).strip()
        if value and value[0] in "\"'" and len(value) >= 2 and value[-1] == value[0]:
            value = value[1:-1]
        else:
            value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
        values[match.group(1)] = value
    return values


def analyze(root: Path, *, production: bool) -> list[Finding]:
    findings: list[Finding] = []
    def add(level: str, code: str, message: str) -> None:
        findings.append(Finding(level, code, message))

    env_file = root / '.env'
    env = dotenv(env_file)
    compose_file = root / 'infra' / 'compose.yaml'
    config_file = root / 'apps/api/tourismo/core/config.py'
    migration = root / 'apps/api/migrations/versions' / f'{LATEST_MIGRATION}.py'
    if not env_file.is_file():
        add('BLOCK' if production else 'NOTE', 'ENV_MISSING', 'Private .env not present in this checkout')
    if not compose_file.is_file():
        add('BLOCK', 'COMPOSE_MISSING', 'Existing infra/compose.yaml is missing')
    if not config_file.is_file():
        add('BLOCK', 'SETTINGS_MISSING', 'Backend settings source is missing')
    if not migration.is_file():
        add('BLOCK', 'PHASE9C_MISSING', f'Phase 9C migration {LATEST_MIGRATION} is not in the source tree')
    else:
        revision = migration.read_text(encoding='utf-8-sig')
        if not re.search(r"(?m)^revision\s*=\s*['\"]0019_notifications_trust['\"]", revision):
            add('BLOCK', 'PHASE9C_MISMATCH', 'Phase 9C migration revision ID does not match')
    if not production:
        add('NOTE', 'LOCAL_ONLY', 'Local mode checks source prerequisites only; use --mode production for deployment blockers')
        return findings

    if env.get('APP_ENVIRONMENT', '').lower() != 'production':
        add('BLOCK', 'ENV_MODE', 'APP_ENVIRONMENT must be production')
    db_url = env.get('DATABASE_URL', '')
    if not db_url:
        add('BLOCK', 'DATABASE_URL', 'DATABASE_URL must be supplied in the private deployment environment')
    elif 'tourismo_dev' in db_url.lower() or 'localhost' in db_url.lower() or '127.0.0.1' in db_url:
        add('BLOCK', 'DEV_DATABASE', 'Database URL still contains a development placeholder or local host')

    for key in ('CLERK_ISSUER', 'CLERK_JWKS_URL'):
        if not env.get(key, '').startswith('https://'):
            add('BLOCK', f'IDENTITY_{key}', f'{key} needs a real HTTPS value')
    if not env.get('VITE_CLERK_PUBLISHABLE_KEY'):
        add('BLOCK', 'CLIENT_AUTH', 'Client Clerk publishable key is missing')
    for key in ('CORS_ORIGINS', 'ALLOWED_AUTH_ORIGINS'):
        origins = [item.strip() for item in env.get(key, '').split(',') if item.strip()]
        if not origins or any(not origin.startswith('https://') for origin in origins):
            add('BLOCK', f'ORIGIN_{key}', f'{key} must list only approved HTTPS origins')
        if any('*' in origin for origin in origins):
            add('BLOCK', f'WILDCARD_{key}', f'{key} must not allow wildcard origins')
    if env.get('ENABLE_DEMO_CATALOG', '').strip().lower() in ('1', 'yes', 'true', 'on'):
        add('BLOCK', 'DEMO_ENABLED', 'Demo catalog must not be publicly enabled')
    if env.get('ENABLE_PHONE_OTP', '').strip().lower() in ('1', 'yes', 'true', 'on'):
        add('BLOCK', 'PHONE_OTP', 'Phone OTP requires a real SMS provider before enabling')
    if not env.get('VENDOR_CLAMAV_HOST'):
        add('BLOCK', 'SCAN_SERVICE', 'No malware scanner host configured for private vendor evidence')
    if not env.get('MAP_TILE_URL', '').startswith('https://'):
        add('BLOCK', 'MAP_TILES', 'Production map tiles need a licensed HTTPS source')

    if compose_file.is_file():
        compose = compose_file.read_text(encoding='utf-8-sig')
        if re.search(r'(?m)^\s*POSTGRES_PASSWORD\s*:\s*tourismo_dev\s*$', compose):
            add('BLOCK', 'STATIC_DB_PASSWORD', 'Development database password is hardcoded in Compose')
        if re.search(r'(?m)^\s*-\s*["\']?(?:0\.0\.0\.0:)?8000:8000["\']?\s*$', compose):
            add('BLOCK', 'DIRECT_PUBLIC_PORT', 'Compose exposes port 8000; deploy behind reviewed TLS proxy/network policy')
    # These cannot be validated from local files; never imply production approval.
    add('MANUAL', 'EDGE_RATE_LIMITS', 'Verify shared rate limits/WAF before more than one replica')
    add('MANUAL', 'RESTORE_DRILL', 'Restore a DB and private documents into an isolated environment and record evidence')
    add('MANUAL', 'TLS_MONITORING', 'Verify TLS, DNS, log redaction, alerts, uptime monitoring and backup encryption')
    add('MANUAL', 'LEGAL_CONTENT', 'Review privacy notices, retention, licenses, translation and image source rights')
    add('MANUAL', 'AUTHZ', 'Perform real Clerk guest/tourist/vendor/admin isolation tests')
    return findings


def git_tracks_env(root: Path) -> bool:
    if not (root / '.git').exists():
        return False
    run = subprocess.run(['git', '-C', str(root), 'ls-files', '--error-unmatch', '.env'],
                         capture_output=True, text=True, check=False)
    return run.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--mode', choices=('local', 'production'), default='local')
    args = parser.parse_args()
    root = args.root.resolve()
    findings = analyze(root, production=args.mode == 'production')
    if git_tracks_env(root):
        findings.append(Finding('BLOCK', 'ENV_TRACKED', 'Private .env is tracked by Git; revoke exposed credentials and stop deployment'))
    print(f'Tourismo Phase 10A configuration audit ({args.mode}). Secret values are never printed.')
    for f in findings:
        print(f'{f.level:6s} [{f.code}] {f.message}')
    count = sum(f.level == 'BLOCK' for f in findings)
    print(f'RESULT: {count} blocking finding(s); {sum(f.level == "MANUAL" for f in findings)} manual launch gates')
    return 2 if count else 0


if __name__ == '__main__':
    raise SystemExit(main())
