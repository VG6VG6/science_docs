from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from config import settings


class WarehouseBase(DeclarativeBase):
    pass


def _sqlite_connect_args(url: str) -> dict | None:
    if url.startswith("sqlite:///") or url.startswith("sqlite://"):
        return {"timeout": 60.0}
    return None


_warehouse_engine_kw: dict = {"echo": False, "future": True}
_ca = _sqlite_connect_args(settings.warehouse_database_url)
if _ca is not None:
    _warehouse_engine_kw["connect_args"] = _ca
warehouse_engine = create_engine(settings.warehouse_database_url, **_warehouse_engine_kw)


@event.listens_for(warehouse_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.close()
    except Exception:
        return


WarehouseSessionLocal = sessionmaker(
    bind=warehouse_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def _migrate_columns() -> None:
    """Добавляет колонки которых может не быть в уже существующих БД."""
    migrations = {
        "warehouse_journals": [
            ("eissn", "VARCHAR"),
        ],
        "warehouse_article_cache": [
            ("scopus_entry", "TEXT"),
            ("scopus_search_meta", "TEXT"),
            ("eissn", "VARCHAR"),
        ],
    }
    with warehouse_engine.begin() as conn:
        for table, columns in migrations.items():
            result = conn.execute(text(f"PRAGMA table_info({table});"))
            existing_cols = {row[1] for row in result.fetchall()}
            for col_name, col_type in columns:
                if col_name not in existing_cols:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                    ))


def init_warehouse_db() -> None:
    import warehouse_models  # noqa: F401

    WarehouseBase.metadata.create_all(bind=warehouse_engine)
    _migrate_columns()


@contextmanager
def get_warehouse_session() -> Session:
    session: Session = WarehouseSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()