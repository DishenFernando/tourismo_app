from collections.abc import Generator
from functools import lru_cache
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import DeclarativeBase, Session
from tourismo.core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    # Lazy creation lets stateless public preview routes run with no DB driver/connection.
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def get_db() -> Generator[Session, None, None]:
    with Session(get_engine(), autoflush=False, expire_on_commit=False) as session:
        yield session
