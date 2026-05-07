from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from scopus_client import (
    get_scopus_metadata,
    search_articles_by_author,
    ScopusMetadata,
    ScopusError,
    AuthorSearchResult,
)
from warehouse_db import get_warehouse_session, init_warehouse_db
from warehouse_models import ArticleCache, WarehouseJournal
from warehouse_service import (
    get_cached_article,
    match_metric,
    upsert_article_cache,
    get_cached_author_search,
    save_author_search_cache,
    author_cache_to_result,
)


def _build_ranking(session: Session, issn: str | None, eissn: str | None, year: int | None) -> Optional[Dict[str, Any]]:
    """Вспомогательная функция: ищет метрику и формирует словарь ranking."""
    if not (issn or eissn) or not year:
        return None
    journal_rank = match_metric(session=session, issn=issn, eissn=eissn, year=year)
    if not journal_rank:
        return None
    is_fallback_year = journal_rank.year != year
    journal = session.get(WarehouseJournal, journal_rank.journal_id)
    return {
        "issn": journal.issn if journal else None,
        "eissn": journal.eissn if journal else None,
        "title": journal.journal_name if journal else None,
        "year": journal_rank.year,
        "requested_year": year,
        "is_fallback_year": is_fallback_year,
        "quartile": journal_rank.quartile,
        "sjr": journal_rank.sjr,
        "country": journal.country if journal else None,
        "h_index": journal_rank.h_index,
        "is_white_list": journal_rank.is_white_list,
        "vak_category": journal_rank.vak_category,
    }


def _row_to_scopus_metadata(row: ArticleCache) -> ScopusMetadata:
    return ScopusMetadata(
        title=row.scopus_title,
        issn=row.issn,
        eissn=row.eissn,
        publication_year=row.publication_year,
        journal_name=row.journal_name,
        raw_entry=row.scopus_entry,
        search_meta=row.scopus_search_meta,
    )


def _extract_authors_from_raw_entry(raw_entry: Dict[str, Any] | str | None) -> List[str]:
    """Extract author names from cached Scopus entry payload."""
    if isinstance(raw_entry, str):
        try:
            raw_entry = json.loads(raw_entry)
        except (TypeError, ValueError):
            return []
    if not isinstance(raw_entry, dict):
        return []
    authors_raw = raw_entry.get("author", [])
    if not isinstance(authors_raw, list):
        authors_raw = [authors_raw]

    authors: List[str] = []
    for author in authors_raw:
        if not isinstance(author, dict):
            continue
        name = author.get("authname") or author.get("ce:indexed-name") or ""
        if name:
            authors.append(str(name))
    if authors:
        return authors

    # Fallback for short title-search payloads where only creator is provided.
    creator = raw_entry.get("dc:creator")
    if isinstance(creator, str) and creator.strip():
        return [creator.strip()]
    return authors


def verify_article_core(
    session: Session, title: str, max_results: int = 25
) -> List[Dict[str, Any]]:
    """Same pipeline as verify_article but uses an existing session."""
    scopus_error: Optional[str] = None
    metas: List[ScopusMetadata] = []
    limit = min(max(1, max_results), 200)

    cached_rows = get_cached_article(session, title)
    if cached_rows:
        metas = [_row_to_scopus_metadata(r) for r in cached_rows]
        # Legacy cache rows may miss author fields; refresh once from Scopus.
        has_any_authors = any(_extract_authors_from_raw_entry(m.raw_entry) for m in metas)
        # Also refresh when cached rows are fewer than requested limit.
        if (not has_any_authors) or (len(metas) < limit):
            try:
                refreshed = get_scopus_metadata(title, max_results=limit)
            except ScopusError:
                refreshed = []
            if refreshed:
                upsert_article_cache(session, title, refreshed)
                metas = refreshed
    else:
        try:
            metas = get_scopus_metadata(title, max_results=limit)
        except ScopusError as exc:
            scopus_error = str(exc)
        if metas:
            upsert_article_cache(session, title, metas)

    if not metas:
        return [
            {
                "query_title": title,
                "scopus_error": scopus_error,
                "scopus": None,
                "ranking": None,
            }
        ]

    out: List[Dict[str, Any]] = []
    for meta in metas:
        ranking = _build_ranking(
            session,
            issn=meta.issn,
            eissn=meta.eissn,
            year=meta.publication_year,
        )
        out.append(
            {
                "query_title": title,
                "scopus_error": scopus_error,
                "scopus": {
                    "title": meta.title,
                    "issn": meta.issn,
                    "eissn": meta.eissn,
                    "publication_year": meta.publication_year,
                    "journal_name": meta.journal_name,
                    "authors": _extract_authors_from_raw_entry(meta.raw_entry),
                },
                "ranking": ranking,
            }
        )
    return out


def search_by_author_core(
    session: Session,
    author_name: str,
    max_results: Optional[int] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Поиск статей по автору с обогащением каждой статьи метриками журнала.

    Args:
        session: Сессия warehouse DB.
        author_name: Имя автора (фамилия или «Фамилия, И.О.»).
        max_results: Сколько статей запрашивать у Scopus.
        use_cache: Использовать кеш (True по умолчанию). False форсирует
                   обращение к Scopus API.

    Returns:
        Словарь с полями:
          - query_author: str
          - total_found: int  — сколько всего нашёл Scopus
          - from_cache: bool  — взят ли результат из кеша
          - scopus_error: str | None
          - articles: list[dict]  — каждая статья + ranking
    """
    scopus_error: Optional[str] = None
    from_cache = False
    result: Optional[AuthorSearchResult] = None

    # Пробуем кеш
    if use_cache:
        cached_rows = get_cached_author_search(session, author_name)
        if cached_rows is not None:
            cached_result = author_cache_to_result(author_name, cached_rows)
            cached_count = len(cached_result.articles)
            # Cache is considered complete only when it satisfies requested size.
            # For max_results=None we treat it as "need all found".
            if max_results is None:
                cache_complete = cached_count >= cached_result.total_found
            else:
                cache_complete = cached_count >= min(max_results, cached_result.total_found)

            if cache_complete:
                result = cached_result
                from_cache = True

    # Идём в Scopus если кеша нет или он отключён
    if result is None:
        try:
            result = search_articles_by_author(author_name, max_results=max_results)
            save_author_search_cache(session, result)
        except ScopusError as exc:
            scopus_error = str(exc)
            result = AuthorSearchResult(
                query_author=author_name,
                total_found=0,
                articles=[],
                scopus_error=scopus_error,
            )

    # Обогащаем каждую статью метриками журнала
    articles_out: List[Dict[str, Any]] = []
    for article in result.articles:
        ranking = _build_ranking(
            session,
            issn=article.issn,
            eissn=article.eissn,
            year=article.publication_year,
        )
        articles_out.append({
            "title": article.title,
            "issn": article.issn,
            "eissn": article.eissn,
            "publication_year": article.publication_year,
            "journal_name": article.journal_name,
            "authors": article.authors,
            "ranking": ranking,
        })

    return {
        "query_author": author_name,
        "total_found": result.total_found,
        "returned": len(articles_out),
        "from_cache": from_cache,
        "scopus_error": scopus_error,
        "articles": articles_out,
    }


def verify_article(title: str, max_results: int = 25) -> List[Dict[str, Any]]:
    """Verify one article; opens one DB session and commits once."""
    init_warehouse_db()
    with get_warehouse_session() as session:
        return verify_article_core(session, title, max_results=max_results)


def search_by_author(
    author_name: str,
    max_results: Optional[int] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Search articles by author name; opens one DB session and commits once."""
    init_warehouse_db()
    with get_warehouse_session() as session:
        return search_by_author_core(session, author_name, max_results, use_cache)