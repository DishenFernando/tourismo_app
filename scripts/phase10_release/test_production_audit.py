#!/usr/bin/env python3
"""Self-contained regression tests; no Docker, production credentials or network required."""
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest

P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('audit', P / 'production_audit.py')
audit = importlib.util.module_from_spec(spec)
import sys
sys.modules['audit'] = audit
spec.loader.exec_module(audit)


class ProductionAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'infra').mkdir()
        (self.root / 'apps/api/tourismo/core').mkdir(parents=True)
        (self.root / 'apps/api/migrations/versions').mkdir(parents=True)
        (self.root / 'infra/compose.yaml').write_text('services:\n  db:\n    image: postgres:16\n')
        (self.root / 'apps/api/tourismo/core/config.py').write_text('class Settings: pass\n')
        (self.root / 'apps/api/migrations/versions/0019_notifications_trust.py').write_text(
            "revision = '0019_notifications_trust'\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_local_mode_succeeds_with_no_env(self):
        findings = audit.analyze(self.root, production=False)
        self.assertFalse(any(f.level == 'BLOCK' for f in findings))

    def test_missing_migration_blocks(self):
        (self.root / 'apps/api/migrations/versions/0019_notifications_trust.py').unlink()
        self.assertIn('PHASE9C_MISSING', {f.code for f in audit.analyze(self.root, production=False)})

    def test_production_dev_config_fails_without_leaking_secret(self):
        (self.root / '.env').write_text('APP_ENVIRONMENT=development\nDATABASE_URL=postgresql://secret-token@localhost/db\n')
        results = audit.analyze(self.root, production=True)
        codes = {f.code for f in results}
        self.assertIn('ENV_MODE', codes)
        self.assertIn('DEV_DATABASE', codes)
        self.assertNotIn('secret-token', str(results))

    def test_production_minimum_configuration_still_requires_manual_checks(self):
        (self.root / '.env').write_text('\n'.join((
            'APP_ENVIRONMENT=production',
            'DATABASE_URL=postgresql+psycopg://produser:secret@example.internal:5432/db',
            'CLERK_ISSUER=https://identity.example.org',
            'CLERK_JWKS_URL=https://identity.example.org/jwks',
            'VITE_CLERK_PUBLISHABLE_KEY=pk_live_example',
            'CORS_ORIGINS=https://tourismo.example.org',
            'ALLOWED_AUTH_ORIGINS=https://tourismo.example.org',
            'MAP_TILE_URL=https://tiles.example.org/style/{z}/{x}/{y}.png',
            'VENDOR_CLAMAV_HOST=clamav',
            'ENABLE_DEMO_CATALOG=false',
        )))
        results = audit.analyze(self.root, production=True)
        self.assertFalse([f for f in results if f.level == 'BLOCK'])
        self.assertTrue([f for f in results if f.code == 'RESTORE_DRILL'])

    def test_detects_exposed_compose_defaults_and_wildcards(self):
        (self.root / '.env').write_text('CORS_ORIGINS=*\n')
        (self.root / 'infra/compose.yaml').write_text('''services:
  db:
    environment:
      POSTGRES_PASSWORD: tourismo_dev
  app:
    ports:
      - "8000:8000"
''')
        codes = {f.code for f in audit.analyze(self.root, production=True)}
        self.assertTrue({'STATIC_DB_PASSWORD', 'DIRECT_PUBLIC_PORT', 'ORIGIN_CORS_ORIGINS'} <= codes)

    def test_dotenv_does_not_expand_or_echo(self):
        (self.root / '.env').write_text("APP_ENVIRONMENT='production'\nCLERK_JWKS_URL=https://example.org/jwks # ignored\n")
        values = audit.dotenv(self.root / '.env')
        self.assertEqual(values['APP_ENVIRONMENT'], 'production')
        self.assertEqual(values['CLERK_JWKS_URL'], 'https://example.org/jwks')


if __name__ == '__main__':
    unittest.main(verbosity=2)
