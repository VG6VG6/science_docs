from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, echo=False, future=True)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def _ensure_additional_columns() -> None:
    """Ensure extra columns exist in the existing SQLite table.

    Adds:
    - is_white_list (INTEGER as boolean, default 0)
    - vak_category (TEXT, nullable)
    """
    with engine.begin() as conn:
        # Only for SQLite; harmless for others but this code is tuned to your current setup.
        result = conn.execute(text("PRAGMA table_info(journals_ranks);"))
        existing_cols = {row[1] for row in result.fetchall()}

        if "is_white_list" not in existing_cols:
            conn.execute(
                text(
                    "ALTER TABLE journals_ranks "
                    "ADD COLUMN is_white_list INTEGER NOT NULL DEFAULT 0"
                )
            )

        if "vak_category" not in existing_cols:
            conn.execute(
                text(
                    "ALTER TABLE journals_ranks "
                    "ADD COLUMN vak_category TEXT NULL"
                )
            )


def init_db() -> None:
    """Initialize database metadata and run lightweight migrations."""
    # Import models so they are registered with Base.metadata
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_additional_columns()


@contextmanager
def get_session() -> Session:
    """Context manager for database sessions."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

