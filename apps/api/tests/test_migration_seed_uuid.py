"""Regression check for PostgreSQL UUID seed parameters in migration 0001."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from sqlalchemy.dialects import postgresql


def test_initial_migration_casts_seed_uuids(monkeypatch):
    migration_path = Path(__file__).resolve().parents[1] / 'migrations/versions/0001_foundation.py'
    spec = spec_from_file_location('tourismo_migration_0001', migration_path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    statements = []
    monkeypatch.setattr(migration.op, 'execute', statements.append)
    monkeypatch.setattr(migration.op, 'create_table', lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, 'create_index', lambda *args, **kwargs: None)

    migration.upgrade()

    sql = [str(stmt.compile(dialect=postgresql.dialect())) for stmt in statements if not isinstance(stmt, str)]
    destinations = [stmt for stmt in sql if 'INSERT INTO destinations ' in stmt]
    translations = [stmt for stmt in sql if 'INSERT INTO destination_translations ' in stmt]
    assert len(destinations) == 5
    assert len(translations) == 5
    assert all('CAST(%(id)s AS UUID)' in stmt for stmt in destinations)
    assert all('CAST(%(id)s AS UUID)' in stmt and 'CAST(%(destination_id)s AS UUID)' in stmt
               for stmt in translations)
