from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Корень проекта — там, где лежит этот файл
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "bin" / "science_docs.db"
CSV_DIR = PROJECT_ROOT


def update_science_docs_db() -> None:
    """Импортирует данные из scimagojr CSV-файлов в journals_ranks.

    Поле «Issn» в CSV содержит либо два значения через запятую
    («15424863, 00079235»), либо одно. Порядок в scimagojr: первое —
    print ISSN, второе — eISSN. Если значение одно, природа неизвестна
    (бывают online-only журналы с единственным eISSN), поэтому храним
    его в обоих полях — issn и eissn — чтобы поиск работал в любом случае.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    total_in_db = 0

    for year in range(2020, 2025):
        csv_path = CSV_DIR / f"scimagojr {year}.csv"
        if not csv_path.exists():
            print(f"⚠️  Файл {csv_path.name} не найден, пропускаю.")
            continue

        try:
            df = pd.read_csv(csv_path, sep=";", low_memory=False)
            if len(df.columns) < 5:
                df = pd.read_csv(csv_path, sep=",", low_memory=False)
        except Exception as exc:
            print(f"❌ Ошибка чтения {csv_path.name}: {exc}")
            continue

        needed = ["Title", "Issn", "SJR Best Quartile", "SJR", "Country", "H index"]
        missing = [c for c in needed if c not in df.columns]
        if missing:
            print(f"❌ В {csv_path.name} нет колонок: {missing}, пропускаю.")
            continue

        df = df[needed].copy()
        df["Year"] = year

        rows: list[dict] = []
        for _, row in df.iterrows():
            raw_issn = str(row["Issn"]).strip() if pd.notna(row["Issn"]) else ""
            parts = [s.strip() for s in raw_issn.split(",") if s.strip()]

            if len(parts) >= 2:
                # Стандартный случай: первый — print ISSN, второй — eISSN
                issn, eissn = parts[0], parts[1]
            elif len(parts) == 1:
                # Одно значение — природа неизвестна, пишем в оба поля
                issn = eissn = parts[0]
            else:
                issn = eissn = None

            new_row = row.to_dict()
            new_row["Issn"] = issn
            new_row["eIssn"] = eissn
            rows.append(new_row)

        df_expanded = pd.DataFrame(rows)

        mode = "replace" if year == 2020 else "append"
        df_expanded.to_sql("journals_ranks", conn, if_exists=mode, index=False)

        print(f"  {year}: загружено {len(df_expanded)} журналов.")
        total_in_db += len(df_expanded)

    print(f"\n✅ Импорт завершён. Всего строк в БД: {total_in_db}")

    check_df = pd.read_sql(
        "SELECT Year, COUNT(*) as Count FROM journals_ranks GROUP BY Year ORDER BY Year",
        conn,
    )
    print("\n📊 Строк по годам:")
    print(check_df.to_string(index=False))

    conn.close()


def update_environment(env_file: str) -> bool:
    env_path = PROJECT_ROOT / env_file
    if not env_path.exists():
        print(f"⚠️  Файл окружения не найден: {env_path}")
        return False
    load_dotenv(env_path)
    print(f"✅ Переменные окружения загружены из {env_file}")
    return True


if __name__ == "__main__":
    import argparse
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "app"))

    parser = argparse.ArgumentParser(description="ScienceDocs — управление данными.")
    parser.add_argument(
        "-u", "--update",
        action="store_true",
        help="Импортировать/обновить journals_ranks из scimagojr CSV.",
    )
    parser.add_argument(
        "-r", "--refresh-warehouse",
        action="store_true",
        dest="refresh_warehouse",
        help="Перестроить warehouse DB из journals_ranks (запускать после --update).",
    )
    parser.add_argument(
        "-b", "--batch",
        metavar="INPUT",
        help="Запустить batch-обработку статей из .txt или .xlsx файла.",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="OUTPUT",
        default="report.json",
        help="Путь к выходному JSON-отчёту для --batch (по умолчанию: report.json).",
    )
    parser.add_argument(
        "-e", "--environment",
        metavar="ENV",
        default="bin/info.env",
        help="Путь к файлу с переменными окружения (по умолчанию: bin/info.env).",
    )
    args = parser.parse_args()

    if args.environment:
        print("▶ Загружаем переменные окружения…")
        if not update_environment(args.environment):
            exit(1)
        print()

    if args.update:
        print("▶ Обновляем journals_ranks из CSV…")
        update_science_docs_db()
        print()

    if args.refresh_warehouse:
        print("▶ Перестраиваем warehouse DB…")
        from app.warehouse_refresh import refresh_warehouse_from_legacy
        count = refresh_warehouse_from_legacy()
        print(f"✅ Warehouse обновлён, обработано строк: {count}\n")

    if args.batch:
        print(f"▶ Batch-обработка файла: {args.batch}")
        from app.batch import process_batch
        results = process_batch(args.batch, args.output)
        print(f"✅ Обработано статей: {len(results)}. Отчёт: {args.output}\n")

    if not any([args.update, args.refresh_warehouse, args.batch]):
        parser.print_help()