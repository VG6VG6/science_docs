from __future__ import annotations

from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from models import JournalRank


def _normalize_issn(issn: str) -> str:
    return issn.strip().upper().replace(" ", "")


def _issn_variants(issn: str) -> list[str]:
    """Generate common ISSN representations (with and without hyphen)."""
    s = _normalize_issn(issn)
    compact = s.replace("-", "")
    variants = {s, compact}
    if len(compact) == 8:
        variants.add(f"{compact[:4]}-{compact[4:]}")
    return [v for v in variants if v]


def match_rank(session: Session, issn: str, year: int) -> Optional[JournalRank]:
    """Match a journal rank by ISSN and year with fallback logic.

    Priority:
    1. Exact match on (issn, year).
    2. If missing, choose the record with the maximum year <= requested year.
    3. If still missing, return None.
    """
    if not issn or not year:
        return None
    issn_values = _issn_variants(issn)

    # 1) Try exact match
    stmt_exact = (
        select(JournalRank)
        .where(or_(*[JournalRank.issn == v for v in issn_values]), JournalRank.year == year)
        .limit(1)
    )
    exact = session.scalars(stmt_exact).first()
    if exact:
        return exact

    # 2) Fallback: closest previous year
    stmt_prev = (
        select(JournalRank)
        .where(or_(*[JournalRank.issn == v for v in issn_values]), JournalRank.year <= year)
        .order_by(JournalRank.year.desc())
        .limit(1)
    )
    return session.scalars(stmt_prev).first()

