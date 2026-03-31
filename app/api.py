from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from db import init_db
from service import verify_article
from warehouse_db import init_warehouse_db


app = FastAPI(title="Scientific Publication Verification System")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    init_warehouse_db()


@app.get("/verify")
def verify(title: str = Query(..., description="Article title to verify")):
    """Verify a single article by title.

    Pipeline:
    - Search Scopus for metadata.
    - Match ISSN+year in local DB (Scimago + Russian lists).
    - Return unified JSON with all metrics.
    """
    if not title.strip():
        raise HTTPException(status_code=400, detail="Title must not be empty.")
    return verify_article(title.strip())

