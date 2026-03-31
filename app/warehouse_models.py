from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from warehouse_db import WarehouseBase


class WarehouseJournal(WarehouseBase):
    __tablename__ = "warehouse_journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issn: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    journal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)


class WarehouseJournalMetric(WarehouseBase):
    __tablename__ = "warehouse_journal_metrics"
    __table_args__ = (UniqueConstraint("journal_id", "year", name="uq_journal_metric_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    journal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouse_journals.id"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    quartile: Mapped[str | None] = mapped_column(String, nullable=True)
    sjr: Mapped[float | None] = mapped_column(Float, nullable=True)
    h_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_white_list: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vak_category: Mapped[str | None] = mapped_column(String, nullable=True)
    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class ArticleCache(WarehouseBase):
    __tablename__ = "warehouse_article_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_title: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    scopus_title: Mapped[str | None] = mapped_column(String, nullable=True)
    issn: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    journal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Full Scopus Search API payloads (first hit + search-results metadata without entry[]).
    scopus_entry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scopus_search_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

