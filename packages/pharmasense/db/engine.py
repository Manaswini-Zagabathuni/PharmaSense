"""SQLAlchemy engine construction."""

from sqlalchemy import URL, Engine, create_engine


def build_engine(database_url: URL | str) -> Engine:
    """Create a pooled SQLAlchemy engine using parameterized execution APIs."""
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        future=True,
    )
