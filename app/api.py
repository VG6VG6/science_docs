from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / "bin" / "info.env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

from batch import process_batch
from db import init_db
from service import search_by_author_core, verify_article_core
from warehouse_db import init_warehouse_db, WarehouseSessionLocal

app = FastAPI(title="Scientific Publication Verification System")
WEB_DIR = PROJECT_ROOT / "web"
REQUESTS_DIR = PROJECT_ROOT / "bin" / "requests"


def _load_runtime_environment() -> None:
    env_file = PROJECT_ROOT / "bin" / "info.env"
    if env_file.exists():
        load_dotenv(env_file)


def _verify_via_batch(title: str) -> dict:
    """Create per-request batch files and return the first processed article."""
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    input_path = REQUESTS_DIR / f"request_{stamp}.txt"
    output_path = REQUESTS_DIR / f"report_{stamp}.json"

    input_path.write_text(f"{title}\n", encoding="utf-8")

    results = process_batch(str(input_path), str(output_path))
    if not results:
        raise HTTPException(status_code=500, detail="Batch processing returned no results.")

    result = results[0]
    result["batch_files"] = {
        "input": str(input_path.relative_to(PROJECT_ROOT)),
        "output": str(output_path.relative_to(PROJECT_ROOT)),
    }
    return result


@app.on_event("startup")
def on_startup() -> None:
    _load_runtime_environment()
    init_db()
    init_warehouse_db()


@app.get("/verify")
def verify(title: str = Query(..., description="Article title to verify")):
    """Верифицировать одну статью по названию.

    Pipeline: Scopus API → ISSN → метрики журнала из warehouse.
    """
    if not title.strip():
        raise HTTPException(status_code=400, detail="Title must not be empty.")
    return _verify_via_batch(title.strip())


@app.get("/search/author")
def search_author(
    author: str = Query(..., description="Имя автора. Форматы: 'Иванов' или 'Иванов, И.И.'"),
    limit: int = Query(25, ge=1, le=200, description="Максимальное количество статей (1–200)"),
    refresh: bool = Query(False, description="Игнорировать кеш и запросить Scopus заново"),
):
    """Поиск статей по имени автора.

    Возвращает список статей с метриками журнала (квартиль, SJR, и т.д.)
    для каждой найденной публикации.

    **Формат имени автора:**
    - `Иванов` — поиск только по фамилии (широкий, много результатов)
    - `Иванов, И.И.` — фамилия + инициалы (точнее)
    - `Ivanov, Ivan` — полное имя на латинице

    **Кеширование:** результаты кешируются в warehouse DB. Параметр
    `refresh=true` принудительно обновляет кеш из Scopus.
    """
    name = author.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Author name must not be empty.")

    session = WarehouseSessionLocal()
    try:
        result = search_by_author_core(
            session=session,
            author_name=name,
            max_results=limit,
            use_cache=not refresh,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        session.close()

    return result


@app.get("/")
def frontend_index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")