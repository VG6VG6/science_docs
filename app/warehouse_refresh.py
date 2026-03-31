from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from db import get_session, init_db
from models import JournalRank
from warehouse_db import get_warehouse_session, init_warehouse_db
from warehouse_models import WarehouseJournal, WarehouseJournalMetric


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def refresh_warehouse_from_legacy() -> int:
    """Rebuild/update warehouse DB from current journals_ranks."""
    init_db()
    init_warehouse_db()

    rows_count = 0
    with get_session() as legacy, get_warehouse_session() as warehouse:
        existing_journals = warehouse.scalars(select(WarehouseJournal)).all()
        journal_by_issn = {j.issn: j for j in existing_journals}

        existing_metrics = warehouse.scalars(select(WarehouseJournalMetric)).all()
        metric_by_key = {(m.journal_id, m.year): m for m in existing_metrics}

        rows = legacy.scalars(select(JournalRank)).all()
        for row in rows:
            issn = row.issn or ""
            year = row.year
            if not issn or year is None:
                continue

            journal = journal_by_issn.get(issn)
            if not journal:
                journal = WarehouseJournal(issn=issn, journal_name=row.title, country=row.country)
                warehouse.add(journal)
                warehouse.flush()
                journal_by_issn[issn] = journal
            else:
                if row.title and not journal.journal_name:
                    journal.journal_name = row.title
                if row.country and not journal.country:
                    journal.country = row.country

            metric_key = (journal.id, year)
            metric = metric_by_key.get(metric_key)
            if not metric:
                metric = WarehouseJournalMetric(journal_id=journal.id, year=year)
                warehouse.add(metric)
                metric_by_key[metric_key] = metric

            metric.quartile = row.quartile
            metric.sjr = _to_float(row.sjr)
            metric.h_index = row.h_index
            metric.is_white_list = bool(row.is_white_list) if row.is_white_list is not None else False
            metric.vak_category = row.vak_category
            metric.source_updated_at = datetime.now()
            rows_count += 1
    return rows_count


if __name__ == "__main__":
    imported = refresh_warehouse_from_legacy()
    print(f"Warehouse refreshed, processed rows: {imported}")

