from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

import re

from config import settings


@dataclass
class ScopusMetadata:
    """Normalized fields + full Scopus payload fragments for persistence."""

    title: Optional[str]
    issn: Optional[str]
    publication_year: Optional[int]
    journal_name: Optional[str]
    # First hit from search (full Elsevier document entry as returned by API).
    raw_entry: Optional[Dict[str, Any]] = None
    # search-results block without the heavy "entry" list (totals, links, etc.).
    search_meta: Optional[Dict[str, Any]] = None


class ScopusError(Exception):
    """Domain error for Scopus integration."""


_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def _extract_year_from_cover_date(cover_date: str | None) -> Optional[int]:
    if not cover_date:
        return None
    # cover_date is often like "2023-05-10"
    try:
        return int(cover_date[:4])
    except (TypeError, ValueError):
        return None


def _build_scopus_query(user_query: str) -> str:
    q = user_query.strip()
    if not q:
        return q

    # If it looks like a DOI, use DOI() which is far more precise.
    if _DOI_RE.match(q):
        return f'DOI("{q}")'

    # Otherwise restrict to title to avoid irrelevant matches.
    # Escape quotes by doubling them (Scopus query syntax).
    q_escaped = q.replace('"', '""')
    return f'TITLE("{q_escaped}")'


def _extract_issn(entry: dict[str, Any]) -> Optional[str]:
    # Prefer print ISSN; fallback to eISSN. Some entries return one but not the other.
    issn = entry.get("prism:issn") or entry.get("prism:eIssn") or entry.get("prism:eissn")
    if isinstance(issn, list):
        issn = issn[0] if issn else None
    if issn is None:
        return None
    s = str(issn).strip()
    return s or None


def get_scopus_metadata(query: str) -> Optional[ScopusMetadata]:
    """Search Scopus by article title or DOI and return core metadata.

    Args:
        query: Article title or DOI. The function just passes this into the
               Scopus Search API as a free-text query.

    Returns:
        ScopusMetadata or None if nothing is found or on handled errors.
    """
    if not settings.scopus_api_key:
        # Fail fast but gracefully if no API key is configured.
        raise ScopusError("SCOPUS_API_KEY is not configured in the environment.")

    params = {
        "query": _build_scopus_query(query),
        "count": 1,
    }
    headers = {
        "X-ELS-APIKey": settings.scopus_api_key,
        "Accept": "application/json",
    }

    try:
        resp = requests.get(settings.scopus_api_url, params=params, headers=headers, timeout=15)
    except requests.RequestException as exc:
        # Log or propagate as a domain error; here we return None to be "graceful".
        raise ScopusError(f"Error calling Scopus API: {exc}") from exc

    if resp.status_code != 200:
        # Non-200 is a soft failure, caller can decide what to do.
        raise ScopusError(f"Scopus API returned status {resp.status_code}: {resp.text[:200]}")

    try:
        data: Dict[str, Any] = resp.json()
    except ValueError as exc:
        raise ScopusError("Failed to decode Scopus JSON response") from exc

    entries = (
        data.get("search-results", {})
        .get("entry", [])
    )
    if not entries:
        return None

    search_results = data.get("search-results") or {}
    search_meta = {
        k: v for k, v in search_results.items() if k != "entry"
    }

    entry = entries[0]

    title = entry.get("dc:title")
    issn = _extract_issn(entry)
    cover_date = entry.get("prism:coverDate")
    journal_name = entry.get("prism:publicationName")

    year = _extract_year_from_cover_date(cover_date)

    return ScopusMetadata(
        title=title,
        issn=issn,
        publication_year=year,
        journal_name=journal_name,
        raw_entry=dict(entry),
        search_meta=search_meta if search_meta else None,
    )

