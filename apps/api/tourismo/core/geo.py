"""Minimal PostgreSQL/PostGIS geography type for the Phase 1 schema.

Geographic calculations and MapLibre adapters are implemented in Phase 5.
"""
from sqlalchemy.types import UserDefinedType


class Geography(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return 'geography(Point,4326)'
