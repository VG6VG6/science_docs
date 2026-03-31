from __future__ import annotations

from typing import Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import JournalRank


def _normalize_issn(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Take only first ISSN if multiple separated by comma/semicolon
    if "," in s:
        s = s.split(",", 1)[0]
    if ";" in s:
        s = s.split(";", 1)[0]
    return s


def import_white_list(session: Session, excel_path: str) -> int:
    """Import/update White List flags from an Excel file.

    Expected columns (flexible):
    - 'Issn' or 'ISSN' (case-insensitive) – required
    - 'Title' (optional)

    Behaviour:
    - For each ISSN, set is_white_list=True on all existing rows.
    - If no row exists for that ISSN, create a minimal one with is_white_list=True.
    """
    df = pd.read_excel(excel_path)
    cols = {c.lower(): c for c in df.columns}
    issn_col = cols.get("issn")
    if not issn_col:
        raise ValueError("White List Excel must contain an 'ISSN' column.")

    title_col = cols.get("title")

    updated_count = 0

    for _, row in df.iterrows():
        issn = _normalize_issn(row.get(issn_col))
        if not issn:
            continue

        title = None
        if title_col:
            title_val = row.get(title_col)
            title = str(title_val).strip() if pd.notna(title_val) else None

        stmt = select(JournalRank).where(JournalRank.issn == issn)
        existing = session.scalars(stmt).all()

        if existing:
            for rec in existing:
                if not rec.is_white_list:
                    rec.is_white_list = True
                    updated_count += 1
        else:
            jr = JournalRank(
                title=title,
                issn=issn,
                is_white_list=True,
            )
            session.add(jr)
            updated_count += 1

    return updated_count


def import_vak_list(session: Session, excel_path: str) -> int:
    """Import/update VAK categories from an Excel file.

    Expected columns (flexible):
    - 'Issn' or 'ISSN' – required
    - 'vak_category' or 'VAK' or 'Category' – required (values K1/K2/K3)

    Behaviour:
    - For each ISSN, set vak_category for all existing rows.
    - If no row exists, create a minimal one with vak_category set.
    """
    df = pd.read_excel(excel_path)
    cols = {c.lower(): c for c in df.columns}
    issn_col = cols.get("issn")
    if not issn_col:
        raise ValueError("VAK Excel must contain an 'ISSN' column.")

    vak_col = cols.get("vak_category") or cols.get("vak") or cols.get("category")
    if not vak_col:
        raise ValueError("VAK Excel must contain a vak_category/VAK/Category column.")

    updated_count = 0

    for _, row in df.iterrows():
        issn = _normalize_issn(row.get(issn_col))
        if not issn:
            continue

        raw_cat = row.get(vak_col)
        if pd.isna(raw_cat):
            continue

        vak_category = str(raw_cat).strip().upper()
        if vak_category not in {"K1", "K2", "K3"}:
            # Skip unknown categories instead of corrupting data.
            continue

        stmt = select(JournalRank).where(JournalRank.issn == issn)
        existing = session.scalars(stmt).all()

        if existing:
            for rec in existing:
                rec.vak_category = vak_category
                updated_count += 1
        else:
            jr = JournalRank(
                issn=issn,
                vak_category=vak_category,
            )
            session.add(jr)
            updated_count += 1

    return updated_count

