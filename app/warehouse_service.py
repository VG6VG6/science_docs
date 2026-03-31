from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from scopus_client import ScopusMetadata
from warehouse_models import WarehouseJournal, WarehouseJournalMetric, ArticleCache


def _normalize_issn(issn: str) -> str:
    return issn.strip().upper().replace(" ", "")


def _issn_variants(issn: str) -> list[str]:
    s = _normalize_issn(issn)
    compact = s.replace("-", "")
    variants = {s, compact}
    if len(compact) == 8:
        variants.add(f"{compact[:4]}-{compact[4:]}")
    return [v for v in variants if v]


def get_cached_article(session: Session, query_title: str) -> Optional[ArticleCache]:
    stmt = select(ArticleCache).where(ArticleCache.query_title == query_title).limit(1)
    return session.scalars(stmt).first()


def upsert_article_cache(session: Session, query_title: str, meta: ScopusMetadata) -> ArticleCache:
    cached = get_cached_article(session, query_title)
    if not cached:
        cached = ArticleCache(query_title=query_title)
        session.add(cached)

    cached.scopus_title = meta.title
    cached.issn = meta.issn
    cached.publication_year = meta.publication_year
    cached.journal_name = meta.journal_name
    cached.scopus_entry = meta.raw_entry
    cached.scopus_search_meta = meta.search_meta
    cached.last_checked_at = datetime.utcnow()
    return cached


def match_metric(session: Session, issn: str, year: int) -> Optional[WarehouseJournalMetric]:
    issn_values = _issn_variants(issn)
    stmt_exact = (
        select(WarehouseJournalMetric)
        .join(WarehouseJournal, WarehouseJournal.id == WarehouseJournalMetric.journal_id)
        .where(
            or_(*[WarehouseJournal.issn == v for v in issn_values]),
            WarehouseJournalMetric.year == year,
        )
        .limit(1)
    )
    exact = session.scalars(stmt_exact).first()
    if exact:
        return exact

    stmt_prev = (
        select(WarehouseJournalMetric)
        .join(WarehouseJournal, WarehouseJournal.id == WarehouseJournalMetric.journal_id)
        .where(
            or_(*[WarehouseJournal.issn == v for v in issn_values]),
            WarehouseJournalMetric.year <= year,
        )
        .order_by(WarehouseJournalMetric.year.desc())
        .limit(1)
    )
    return session.scalars(stmt_prev).first()

