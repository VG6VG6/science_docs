import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Application configuration."""

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///science_docs.db")
    warehouse_database_url: str = os.getenv(
        "WAREHOUSE_DATABASE_URL", "sqlite:///science_warehouse.db"
    )
    scopus_api_key: str | None = os.getenv("SCOPUS_API_KEY")
    scopus_api_url: str = os.getenv(
        "SCOPUS_API_URL", "https://api.elsevier.com/content/search/scopus"
    )


settings = Settings()

