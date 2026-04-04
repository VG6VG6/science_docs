import os
from dataclasses import dataclass, field
from pathlib import Path

# Корень проекта — две директории вверх от config.py (app/ -> project_root/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    """Application configuration."""

    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"sqlite:///{PROJECT_ROOT / 'bin' / 'science_docs.db'}"
        )
    )
    warehouse_database_url: str = field(
        default_factory=lambda: os.getenv(
            "WAREHOUSE_DATABASE_URL",
            f"sqlite:///{PROJECT_ROOT / 'bin' / 'science_warehouse.db'}"
        )
    )
    scopus_api_key: str | None = field(
        default_factory=lambda: os.getenv("SCOPUS_API_KEY")
    )
    scopus_api_url: str = field(
        default_factory=lambda: os.getenv(
            "SCOPUS_API_URL", "https://api.elsevier.com/content/search/scopus"
        )
    )

settings = Settings()