"""Ingestion issue and rejected-record audit models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pharmasense.db.base import Base
from pharmasense.db.models.common import CreatedAtMixin

if TYPE_CHECKING:
    from pharmasense.db.models.provenance import IngestionRun, SourceMember


class IngestionIssue(CreatedAtMixin, Base):
    """Aggregated or row-level validation observation with a stable code."""

    __tablename__ = "ingestion_issue"
    __table_args__ = (
        CheckConstraint("occurrence_count >= 1", name="occurrence_count_positive"),
        Index("ix_ingestion_issue_run_code", "ingestion_run_id", "issue_code"),
        Index("ix_ingestion_issue_member_row", "source_member_id", "source_row_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_run.id", ondelete="RESTRICT"), nullable=False
    )
    source_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_member.id", ondelete="RESTRICT")
    )
    source_row_number: Mapped[int | None] = mapped_column(BigInteger)
    logical_table: Mapped[str | None] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    issue_code: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(64))
    value_excerpt: Mapped[str | None] = mapped_column(Text)
    value_sha256: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, object] | None] = mapped_column(JSON)
    occurrence_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)

    ingestion_run: Mapped[IngestionRun] = relationship(back_populates="issues")
    source_member: Mapped[SourceMember | None] = relationship()


class RejectedRecord(CreatedAtMixin, Base):
    """A source row that was preserved in quarantine rather than silently dropped."""

    __tablename__ = "rejected_record"
    __table_args__ = (
        UniqueConstraint("ingestion_run_id", "source_member_id", "source_row_number"),
        Index("ix_rejected_record_run_table", "ingestion_run_id", "logical_table"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_run.id", ondelete="RESTRICT"), nullable=False
    )
    source_member_id: Mapped[int] = mapped_column(
        ForeignKey("source_member.id", ondelete="RESTRICT"), nullable=False
    )
    source_row_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    logical_table: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_record_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text)
    issue_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    ingestion_run: Mapped[IngestionRun] = relationship(back_populates="rejected_rows")
    source_member: Mapped[SourceMember] = relationship()
