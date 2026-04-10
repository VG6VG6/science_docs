from app.warehouse_db import warehouse_engine
from sqlalchemy import text
with warehouse_engine.connect() as conn:
    print([r[1] for r in conn.execute(text("PRAGMA table_info(warehouse_author_search_cache);")).fetchall()])
