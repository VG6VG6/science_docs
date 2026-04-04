from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from scopus_client import get_scopus_metadata, ScopusMetadata, ScopusError
from warehouse_db import get_warehouse_session, init_warehouse_db
from warehouse_models import WarehouseJournal
from warehouse_service import get_cached_article, match_metric, upsert_article_cache


def verify_article_core(session: Session, title: str) -> Dict[str, Any]:
    """Same pipeline as verify_article but uses an existing session (one commit per caller)."""
    scopus_error: Optional[str] = None
    scopus_data: Optional[ScopusMetadata] = None

    cached = get_cached_article(session, title)
    if cached:
        scopus_data = ScopusMetadata(
            title=cached.scopus_title,
            issn=cached.issn,
            eissn=cached.eissn,          # eissn теперь тоже берём из кеша
            publication_year=cached.publication_year,
            journal_name=cached.journal_name,
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

    journal_rank = None
    journal = None
    if scopus_data and (scopus_data.issn or scopus_data.eissn) and scopus_data.publication_year:
        journal_rank = match_metric(
            session=session,
            issn=scopus_data.issn,
            eissn=scopus_data.eissn,
            year=scopus_data.publication_year,
        )
        if journal_rank:
            journal = session.get(WarehouseJournal, journal_rank.journal_id)

    return {
        "query_title": title,
        "scopus_error": scopus_error,
        "scopus": {
            "title": scopus_data.title if scopus_data else None,
            "issn": scopus_data.issn if scopus_data else None,
            "eissn": scopus_data.eissn if scopus_data else None,
            "publication_year": scopus_data.publication_year if scopus_data else None,
            "journal_name": scopus_data.journal_name if scopus_data else None,
        },
        "ranking": {
            "issn": journal.issn if journal_rank and journal else None,
            "eissn": journal.eissn if journal_rank and journal else None,
            "title": journal.journal_name if journal_rank and journal else None,
            "year": journal_rank.year if journal_rank else None,
            "quartile": journal_rank.quartile if journal_rank else None,
            "sjr": journal_rank.sjr if journal_rank else None,
            "country": journal.country if journal_rank and journal else None,
            "h_index": journal_rank.h_index if journal_rank else None,
            "is_white_list": journal_rank.is_white_list if journal_rank else None,
            "vak_category": journal_rank.vak_category if journal_rank else None,
        } if journal_rank else None,
    }


def verify_article(title: str) -> Dict[str, Any]:
    """Verify one article; opens one DB session and commits once."""
    init_warehouse_db()
    with get_warehouse_session() as session:
        return verify_article_core(session, title)