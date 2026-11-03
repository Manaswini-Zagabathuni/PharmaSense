"""Shared model types and immutable-source conventions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column


def source_identifier(length: int) -> mysql.VARCHAR:
    """Return an ASCII identifier type sized to FDA's documented source limits."""

    return mysql.VARCHAR(length=length, charset="ascii")  # type: ignore[no-untyped-call]


class CreatedAtMixin:
    """UTC-by-convention creation timestamp for append-only source records."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
