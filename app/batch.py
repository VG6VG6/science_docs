from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

import json
import pandas as pd

from db import init_db
from service import verify_article_core
from warehouse_db import WarehouseSessionLocal, init_warehouse_db

# Commit every N rows so one huge transaction does not hold the SQLite write lock too long.
_BATCH_COMMIT_EVERY = 100


def _load_titles_from_txt(path: Path) -> list[str]:
    titles: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            t = line.strip()
            if t:
                titles.append(t)
    return titles


def _load_titles_from_xlsx(path: Path) -> list[str]:
    df = pd.read_excel(path)
    if "title" in {c.lower() for c in df.columns}:
        # Use explicit "title" column if present (case-insensitive)
        cols = {c.lower(): c for c in df.columns}
        title_col = cols["title"]
        series = df[title_col]
    else:
        # Fallback: first column
        series = df.iloc[:, 0]

    titles = [str(v).strip() for v in series if pd.notna(v) and str(v).strip()]
    return titles


def process_batch(input_path: str, output_path: str = "report.json") -> List[Dict[str, Any]]:
    """Process a list of article titles from .txt or .xlsx and write JSON report."""
    # Ensure optional columns (is_white_list, vak_category) exist before querying.
    init_db()
    init_warehouse_db()

    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(path)

    ext = path.suffix.lower()
    if ext == ".txt":
        titles = _load_titles_from_txt(path)
    elif ext in {".xlsx", ".xls"}:
        titles = _load_titles_from_xlsx(path)
    else:
        raise ValueError("Unsupported input format. Use .txt or .xlsx")

    results: list[dict[str, Any]] = []
    session = WarehouseSessionLocal()
    try:
        for i, title in enumerate(titles):
            results.append(verify_article_core(session, title))
            if (i + 1) % _BATCH_COMMIT_EVERY == 0:
                session.commit()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    out_path = Path(output_path)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch verify scientific articles.")
    parser.add_argument("input_path", help="Path to .txt or .xlsx file with article titles.")
    parser.add_argument(
        "--output",
        dest="output_path",
        default="report.json",
        help="Path to output JSON report (default: report.json).",
    )
    args = parser.parse_args()

    process_batch(args.input_path, args.output_path)

