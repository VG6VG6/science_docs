from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from config import settings


@dataclass
class ScopusMetadata:
    """Normalized fields + full Scopus payload fragments for persistence."""

    title: Optional[str]
    issn: Optional[str]
    eissn: Optional[str]
    publication_year: Optional[int]
    journal_name: Optional[str]
    authors: List[str] = field(default_factory=list)
    # First hit from search (full Elsevier document entry as returned by API).
    raw_entry: Optional[Dict[str, Any]] = None
    # search-results block without the heavy "entry" list (totals, links, etc.).
    search_meta: Optional[Dict[str, Any]] = None


@dataclass
class AuthorArticle:
    """Одна статья из результатов поиска по автору."""

    title: Optional[str]
    issn: Optional[str]
    eissn: Optional[str]
    publication_year: Optional[int]
    journal_name: Optional[str]
    # Список авторов в том виде, в каком вернул Scopus
    authors: List[str] = field(default_factory=list)
    raw_entry: Optional[Dict[str, Any]] = None


@dataclass
class AuthorSearchResult:
    """Результат поиска по автору: список статей + мета-информация о запросе."""

    query_author: str
    total_found: int
    articles: List[AuthorArticle]
    scopus_error: Optional[str] = None


class ScopusError(Exception):
    """Domain error for Scopus integration."""


_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def _extract_year_from_cover_date(cover_date: str | None) -> Optional[int]:
    if not cover_date:
        return None
    try:
        return int(cover_date[:4])
    except (TypeError, ValueError):
        return None


def _build_title_query(user_query: str) -> str:
    q = user_query.strip()
    if not q:
        return q
    if _DOI_RE.match(q):
        return f'DOI("{q}")'
    q_escaped = q.replace('"', '""')
    return f'TITLE("{q_escaped}")'


def _build_author_query(author_name: str) -> str:
    """Строит Scopus-запрос для поиска по имени автора.

    Scopus поддерживает AUTHOR-NAME(фамилия, имя) — наиболее точный вариант.
    Если передана строка без запятой (только фамилия), используем её как есть.
    """
    name = author_name.strip()
    name_escaped = name.replace('"', '""')
    return f'AUTHOR-NAME("{name_escaped}")'


def _parse_authors(entry: Dict[str, Any]) -> List[str]:
    """Извлекает список авторов из Scopus entry."""
    # Scopus может возвращать авторов в разных полях
    authors_raw = entry.get("author") or entry.get("dc:creator") or []
    
    if not isinstance(authors_raw, list):
        # Иногда Scopus возвращает один объект вместо списка
        authors_raw = [authors_raw]
    
    result = []
    for a in authors_raw:
        if isinstance(a, dict):
            name = a.get("authname") or a.get("ce:indexed-name") or ""
        else:
            # dc:creator может быть просто строкой
            name = str(a) if a else ""
        
        if name:
            result.append(name)
    
    return result


def _parse_entry_to_author_article(entry: Dict[str, Any]) -> AuthorArticle:
    """Разбирает одну Scopus entry в AuthorArticle."""
    return AuthorArticle(
        title=entry.get("dc:title"),
        issn=entry.get("prism:issn"),
        eissn=entry.get("prism:eIssn"),
        publication_year=_extract_year_from_cover_date(entry.get("prism:coverDate")),
        journal_name=entry.get("prism:publicationName"),
        authors=_parse_authors(entry),
        raw_entry=dict(entry),
    )


def _scopus_request(params: dict) -> Dict[str, Any]:
    """Выполняет запрос к Scopus Search API и возвращает распарсенный JSON."""
    if not settings.scopus_api_key:
        raise ScopusError("SCOPUS_API_KEY is not configured in the environment.")

    headers = {
        "X-ELS-APIKey": settings.scopus_api_key,
        "Accept": "application/json",
    }
    try:
        resp = requests.get(
            settings.scopus_api_url,
            params=params,
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise ScopusError(f"Error calling Scopus API: {exc}") from exc

    if resp.status_code != 200:
        raise ScopusError(
            f"Scopus API returned status {resp.status_code}: {resp.text[:200]}"
        )

    try:
        data = resp.json()
        print("----- SCOPUS API RESPONSE -----")
        import json
        print(json.dumps(data, indent=2))
        print("-------------------------------")
        return data
    except ValueError as exc:
        raise ScopusError("Failed to decode Scopus JSON response") from exc


def get_scopus_metadata(query: str) -> Optional[ScopusMetadata]:
    """Search Scopus by article title or DOI and return core metadata."""
    data = _scopus_request({
        "query": _build_title_query(query),
        "count": 1,
    })

    entries = data.get("search-results", {}).get("entry", [])
    if not entries:
        return None

    search_results = data.get("search-results") or {}
    search_meta = {k: v for k, v in search_results.items() if k != "entry"}

    entry = entries[0]
    return ScopusMetadata(
        title=entry.get("dc:title"),
        issn=entry.get("prism:issn"),
        eissn=entry.get("prism:eIssn"),
        publication_year=_extract_year_from_cover_date(entry.get("prism:coverDate")),
        journal_name=entry.get("prism:publicationName"),
        authors=_parse_authors(entry),
        raw_entry=dict(entry),
        search_meta=search_meta if search_meta else None,
    )


def search_articles_by_author(
    author_name: str,
    max_results: Optional[int] = None,
) -> AuthorSearchResult:
    """Ищет статьи по имени автора в Scopus.

    Args:
        author_name: Имя автора.
        max_results: Максимальное количество возвращаемых статей. Если None — извлекаются все.

    Returns:
        AuthorSearchResult со списком найденных статей.
    """
    entries = []
    start = 0
    total = 0
    
    # Scopus API free tier API limit is max 25 per request
    chunk_size = 25 if max_results is None or max_results > 25 else max_results

    while True:
        data = _scopus_request({
            "query": _build_author_query(author_name),
            "count": chunk_size,
            "start": start,
            "field": "dc:title,prism:issn,prism:eIssn,prism:coverDate,"
                     "prism:publicationName,author",
        })

        search_results = data.get("search-results") or {}
        batch_entries = search_results.get("entry", [])

        # Scopus возвращает {"error": "Result set was empty"} вместо пустого списка
        if batch_entries and isinstance(batch_entries[0], dict) and "error" in batch_entries[0]:
            batch_entries = []

        if not batch_entries:
            break
            
        entries.extend(batch_entries)

        if start == 0:
            total_str = search_results.get("opensearch:totalResults", "0")
            try:
                total = int(total_str)
            except (ValueError, TypeError):
                total = 0
                
        # Если мы скачали всё что есть или достигли лимита
        if len(entries) >= total:
            break
            
        if max_results is not None and len(entries) >= max_results:
            entries = entries[:max_results]
            break
            
        start += len(batch_entries)
        
        # Пересчитываем размер следующего куска если есть лимит
        if max_results is not None:
            chunk_size = min(25, max_results - len(entries))

    articles = [_parse_entry_to_author_article(e) for e in entries]

    return AuthorSearchResult(
        query_author=author_name,
        total_found=total,
        articles=articles,
    )


if __name__ == "__main__":
    ans = get_scopus_metadata("Acta Crystallographica Section D: Structural Biology")
    print("Title:", ans.title)
    print("ISSN:", ans.issn)
    print("eISSN:", ans.eissn)
    print("Year:", ans.publication_year)
    print("journal:", ans.journal_name)