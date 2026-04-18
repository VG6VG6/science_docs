from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, or_, delete
from sqlalchemy.orm import Session

from scopus_client import ScopusMetadata, AuthorSearchResult, AuthorArticle
from warehouse_models import (
    WarehouseJournal,
    WarehouseJournalMetric,
    ArticleCache,
    AuthorSearchCache,
)


def _normalize_issn(issn: str) -> str:
    return issn.strip().upper().replace(" ", "")


def _issn_variants(issn: str) -> list[str]:
    s = _normalize_issn(issn)
    compact = s.replace("-", "")
    variants = {s, compact}
    if len(compact) == 8:
        variants.add(f"{compact[:4]}-{compact[4:]}")
    return [v for v in variants if v]


# ---------------------------------------------------------------------------
# Article cache
# ---------------------------------------------------------------------------

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
    cached.authors = meta.authors
    cached.scopus_entry = meta.raw_entry
    cached.scopus_search_meta = meta.search_meta
    cached.last_checked_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Author search cache
# ---------------------------------------------------------------------------

def get_cached_author_search(
    session: Session,
    query_author: str,
) -> Optional[List[AuthorSearchCache]]:
    """Возвращает закешированные строки для автора или None если кеша нет."""
    rows = session.scalars(
        select(AuthorSearchCache).where(AuthorSearchCache.query_author == query_author)
    ).all()
    return list(rows) if rows else None


def save_author_search_cache(
    session: Session,
    result: AuthorSearchResult,
) -> None:
    """Сохраняет результаты поиска по автору, заменяя старые данные."""
    # Удаляем устаревший кеш для этого автора
    session.execute(
        delete(AuthorSearchCache).where(
            AuthorSearchCache.query_author == result.query_author
        )
    )

    now = datetime.now(timezone.utc)
    for article in result.articles:
        row = AuthorSearchCache(
            query_author=result.query_author,
            total_found=result.total_found,
            article_title=article.title,
            issn=article.issn,
            eissn=article.eissn,
            publication_year=article.publication_year,
            journal_name=article.journal_name,
            authors=article.authors,
            cached_at=now,
        )
        session.add(row)


def author_cache_to_result(
    query_author: str,
    rows: List[AuthorSearchCache],
) -> AuthorSearchResult:
    """Восстанавливает AuthorSearchResult из строк кеша."""
    total = rows[0].total_found if rows else 0
    articles = [
        AuthorArticle(
            title=r.article_title,
            issn=r.issn,
            eissn=r.eissn,
            publication_year=r.publication_year,
            journal_name=r.journal_name,
            authors=r.authors or [],
        )
        for r in rows
    ]
    return AuthorSearchResult(
        query_author=query_author,
        total_found=total,
        articles=articles,
    )


# ---------------------------------------------------------------------------
# Journal metric matching
# ---------------------------------------------------------------------------

def match_metric(
    session: Session,
    issn: str | None,
    eissn: str | None,
    year: int,
) -> Optional[WarehouseJournalMetric]:
    """Ищет метрику журнала по ISSN и/или eISSN за указанный год.

    Логика:
    1. Точное совпадение по году — ищем по issn ИЛИ eissn в обоих полях таблицы.
    2. Fallback: ближайший предыдущий год.
    """
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

    stmt_exact = (
        select(WarehouseJournalMetric)
        .join(WarehouseJournal, WarehouseJournal.id == WarehouseJournalMetric.journal_id)
        .where(or_(*issn_conditions), WarehouseJournalMetric.year == year)
        .limit(1)
    )
    exact = session.scalars(stmt_exact).first()
    if exact:
        return exact

    stmt_prev = (
        select(WarehouseJournalMetric)
        .join(WarehouseJournal, WarehouseJournal.id == WarehouseJournalMetric.journal_id)
        .where(or_(*issn_conditions), WarehouseJournalMetric.year <= year)
        .order_by(WarehouseJournalMetric.year.desc())
        .limit(1)
    )
    return session.scalars(stmt_prev).first()