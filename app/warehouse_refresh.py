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


def _journal_key(issn: str | None, eissn: str | None) -> tuple:
    """Ключ дедупликации журнала. Используем пару (issn, eissn)."""
    return (issn or "", eissn or "")


def refresh_warehouse_from_legacy() -> int:
    """Rebuild/update warehouse DB from current journals_ranks."""
    init_db()
    init_warehouse_db()

    rows_count = 0
    with get_session() as legacy, get_warehouse_session() as warehouse:
        existing_journals = warehouse.scalars(select(WarehouseJournal)).all()
        # Индексируем по паре (issn, eissn) — основной ключ дедупликации.
        # Дополнительно индексируем по каждому отдельному значению для быстрого
        # поиска в случае когда Scopus возвращает только один из двух идентификаторов.
        journal_by_key: dict[tuple, WarehouseJournal] = {}
        journal_by_issn: dict[str, WarehouseJournal] = {}
        journal_by_eissn: dict[str, WarehouseJournal] = {}
        for j in existing_journals:
            journal_by_key[_journal_key(j.issn, j.eissn)] = j
            if j.issn:
                journal_by_issn[j.issn] = j
            if j.eissn:
                journal_by_eissn[j.eissn] = j

        existing_metrics = warehouse.scalars(select(WarehouseJournalMetric)).all()
        metric_by_key = {(m.journal_id, m.year): m for m in existing_metrics}

        rows = legacy.scalars(select(JournalRank)).all()
        for row in rows:
            issn = row.issn or None
            eissn = row.eissn or None
            year = row.year

            # Пропускаем строки без хоть какого-то идентификатора
            if not issn and not eissn:
                continue
            if year is None:
                continue

            # Ищем существующий журнал: сначала по паре, потом по каждому отдельно
            key = _journal_key(issn, eissn)
            journal = (
                journal_by_key.get(key)
                or (journal_by_issn.get(issn) if issn else None)
                or (journal_by_eissn.get(eissn) if eissn else None)
            )

            if not journal:
                journal = WarehouseJournal(
                    issn=issn,
                    eissn=eissn,
                    journal_name=row.title,
                    country=row.country,
                )
                warehouse.add(journal)
                warehouse.flush()
                # Регистрируем во всех индексах
                journal_by_key[key] = journal
                if issn:
                    journal_by_issn[issn] = journal
                if eissn:
                    journal_by_eissn[eissn] = journal
            else:
                if row.title and not journal.journal_name:
                    journal.journal_name = row.title
                if row.country and not journal.country:
                    journal.country = row.country
                # Дополняем недостающие идентификаторы если нашли журнал по одному из них
                if issn and not journal.issn:
                    journal.issn = issn
                    journal_by_issn[issn] = journal
                if eissn and not journal.eissn:
                    journal.eissn = eissn
                    journal_by_eissn[eissn] = journal

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