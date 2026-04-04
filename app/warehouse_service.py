from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from scopus_client import ScopusMetadata
from warehouse_models import WarehouseJournal, WarehouseJournalMetric, ArticleCache


def _normalize_issn(issn: str) -> str:
    return issn.strip().upper().replace(" ", "")


def _issn_variants(issn: str) -> list[str]:
    """Возвращает все представления ISSN: с дефисом, без дефиса."""
    s = _normalize_issn(issn)
    compact = s.replace("-", "")
    variants = {s, compact}
    if len(compact) == 8:
        variants.add(f"{compact[:4]}-{compact[4:]}")
    return [v for v in variants if v]


def get_cached_article(session: Session, query_title: str) -> Optional[ArticleCache]:
    stmt = select(ArticleCache).where(ArticleCache.query_title == query_title).limit(1)
    return session.scalars(stmt).first()


def upsert_article_cache(session: Session, query_title: str, meta: ScopusMetadata) -> None:
    if not meta:
        return

    cached = session.query(ArticleCache).filter(
        ArticleCache.query_title == query_title
    ).first()

    if not cached:
        cached = ArticleCache(query_title=query_title)
        session.add(cached)

    cached.scopus_title = meta.title
    cached.issn = meta.issn
    cached.eissn = meta.eissn
    cached.publication_year = meta.publication_year
    cached.journal_name = meta.journal_name
    cached.scopus_entry = meta.raw_entry
    cached.scopus_search_meta = meta.search_meta
    cached.last_checked_at = datetime.now(timezone.utc)


def match_metric(
    session: Session,
    issn: str | None,
    eissn: str | None,
    year: int,
) -> Optional[WarehouseJournalMetric]:
    """Ищет метрику журнала по ISSN и/или eISSN за указанный год.

    Логика поиска:
    1. Точное совпадение по году — ищем по любому из доступных идентификаторов
       (issn ИЛИ eissn), без AND между ними, чтобы не терять журналы,
       у которых в БД и в Scopus разные из пары идентификаторов.
    2. Если не нашли — берём ближайший предыдущий год (fallback).
    """
    # Строим список условий по всем доступным идентификаторам
    issn_conditions = []
    if issn:
        for v in _issn_variants(issn):
            issn_conditions.append(WarehouseJournal.issn == v)
            issn_conditions.append(WarehouseJournal.eissn == v)
    if eissn:
        for v in _issn_variants(eissn):
            issn_conditions.append(WarehouseJournal.issn == v)
            issn_conditions.append(WarehouseJournal.eissn == v)

    if not issn_conditions:
        return None

    # 1. Точное совпадение по году
    stmt_exact = (
        select(WarehouseJournalMetric)
        .join(WarehouseJournal, WarehouseJournal.id == WarehouseJournalMetric.journal_id)
        .where(
            or_(*issn_conditions),
            WarehouseJournalMetric.year == year,
        )
        .limit(1)
    )
    exact = session.scalars(stmt_exact).first()
    if exact:
        return exact

    # 2. Fallback: ближайший год не позже запрошенного
    stmt_prev = (
        select(WarehouseJournalMetric)
        .join(WarehouseJournal, WarehouseJournal.id == WarehouseJournalMetric.journal_id)
        .where(
            or_(*issn_conditions),
            WarehouseJournalMetric.year <= year,
        )
        .order_by(WarehouseJournalMetric.year.desc())
        .limit(1)
    )
    return session.scalars(stmt_prev).first()