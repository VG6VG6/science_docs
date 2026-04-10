from __future__ import annotations

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
from warehouse_models import WarehouseJournal
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
    journal = session.get(WarehouseJournal, journal_rank.journal_id)
    return {
        "issn": journal.issn if journal else None,
        "eissn": journal.eissn if journal else None,
        "title": journal.journal_name if journal else None,
        "year": journal_rank.year,
        "quartile": journal_rank.quartile,
        "sjr": journal_rank.sjr,
        "country": journal.country if journal else None,
        "h_index": journal_rank.h_index,
        "is_white_list": journal_rank.is_white_list,
        "vak_category": journal_rank.vak_category,
    }


def verify_article_core(session: Session, title: str) -> Dict[str, Any]:
    """Same pipeline as verify_article but uses an existing session."""
    scopus_error: Optional[str] = None
    scopus_data: Optional[ScopusMetadata] = None

    cached = get_cached_article(session, title)
    if cached:
        scopus_data = ScopusMetadata(
            title=cached.scopus_title,
            issn=cached.issn,
            eissn=cached.eissn,
            publication_year=cached.publication_year,
            journal_name=cached.journal_name,
            authors=cached.authors or [],
            raw_entry=cached.scopus_entry,
            search_meta=cached.scopus_search_meta,
        )
    else:
        try:
            scopus_data = get_scopus_metadata(title)
        except ScopusError as exc:
            scopus_error = str(exc)
        if scopus_data:
            upsert_article_cache(session, title, scopus_data)

    ranking = None
    if scopus_data:
        ranking = _build_ranking(
            session,
            issn=scopus_data.issn,
            eissn=scopus_data.eissn,
            year=scopus_data.publication_year,
        )

    return {
        "query_title": title,
        "scopus_error": scopus_error,
        "scopus": {
            "title": scopus_data.title if scopus_data else None,
            "issn": scopus_data.issn if scopus_data else None,
            "eissn": scopus_data.eissn if scopus_data else None,
            "publication_year": scopus_data.publication_year if scopus_data else None,
            "journal_name": scopus_data.journal_name if scopus_data else None,
            "authors": scopus_data.authors if scopus_data else [],
        },
        "ranking": ranking,
    }


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
            result = author_cache_to_result(author_name, cached_rows)
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


def verify_article(title: str) -> Dict[str, Any]:
    """Verify one article; opens one DB session and commits once."""
    init_warehouse_db()
    with get_warehouse_session() as session:
        return verify_article_core(session, title)


def search_by_author(
    author_name: str,
    max_results: Optional[int] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Search articles by author name; opens one DB session and commits once."""
    init_warehouse_db()
    with get_warehouse_session() as session:
        return search_by_author_core(session, author_name, max_results, use_cache)