from __future__ import annotations

from sqlalchemy import Integer, String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class JournalRank(Base):
    __tablename__ = "journals_ranks"

    # Table was originally created via pandas.to_sql without an id column,
    # so we map a composite primary key over existing fields.
    title: Mapped[str | None] = mapped_column(String, primary_key=True, nullable=True)
    issn: Mapped[str | None] = mapped_column(String, primary_key=True, nullable=True, index=True)
    quartile: Mapped[str | None] = mapped_column("SJR Best Quartile", String, nullable=True)
    sjr: Mapped[float | None] = mapped_column("SJR", Float, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    h_index: Mapped[int | None] = mapped_column("H index", Integer, nullable=True)
    year: Mapped[int | None] = mapped_column("Year", Integer, primary_key=True, nullable=True, index=True)

    # Russian-specific fields
    is_white_list: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vak_category: Mapped[str | None] = mapped_column(String, nullable=True)  # K1, K2, K3

