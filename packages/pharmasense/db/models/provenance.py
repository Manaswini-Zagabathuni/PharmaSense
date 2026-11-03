"""Source artifact and ingestion-run provenance models."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pharmasense.db.base import Base
from pharmasense.db.models.common import CreatedAtMixin

if TYPE_CHECKING:
    from pharmasense.db.models.faers import FaersCase, FaersReportVersion
    from pharmasense.db.models.quality import IngestionIssue, RejectedRecord


class SourceArtifact(CreatedAtMixin, Base):
    """One immutable archive downloaded from an official source."""

    __tablename__ = "source_artifact"
    __table_args__ = (
        UniqueConstraint("sha256"),
        CheckConstraint("source_quarter BETWEEN 1 AND 4", name="source_quarter_range"),
        CheckConstraint("byte_size >= 0", name="byte_size_nonnegative"),
        Index("ix_source_artifact_period", "source_system", "source_year", "source_quarter"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)
    source_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source_quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    archive_format: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    landing_page_url: Mapped[str | None] = mapped_column(Text)
    posted_date: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    members: Mapped[list[SourceMember]] = relationship(
        back_populates="artifact", passive_deletes=True
    )
    ingestion_runs: Mapped[list[IngestionRun]] = relationship(
        back_populates="artifact", passive_deletes=True
    )


class SourceMember(CreatedAtMixin, Base):
    """One file member within an immutable source artifact."""

    __tablename__ = "source_member"
    __table_args__ = (
        UniqueConstraint("artifact_id", "member_path"),
        CheckConstraint("uncompressed_bytes >= 0", name="uncompressed_bytes_nonnegative"),
        CheckConstraint("compressed_bytes >= 0", name="compressed_bytes_nonnegative"),
        CheckConstraint("row_count IS NULL OR row_count >= 0", name="row_count_nonnegative"),
        Index("ix_source_member_artifact_logical_table", "artifact_id", "logical_table"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey("source_artifact.id", ondelete="RESTRICT"), nullable=False
    )
    logical_table: Mapped[str | None] = mapped_column(String(16))
    member_path: Mapped[str] = mapped_column(String(512), nullable=False)
    uncompressed_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compressed_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    crc32: Mapped[str] = mapped_column(String(8), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    header: Mapped[list[str] | None] = mapped_column(JSON)
    row_count: Mapped[int | None] = mapped_column(BigInteger)

    artifact: Mapped[SourceArtifact] = relationship(back_populates="members")


class IngestionRun(CreatedAtMixin, Base):
    """One append-only attempt to process an immutable artifact."""

    __tablename__ = "ingestion_run"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        CheckConstraint("accepted_records >= 0", name="accepted_records_nonnegative"),
        CheckConstraint("rejected_records >= 0", name="rejected_records_nonnegative"),
        CheckConstraint("warning_count >= 0", name="warning_count_nonnegative"),
        Index("ix_ingestion_run_artifact_status", "artifact_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey("source_artifact.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    code_revision: Mapped[str | None] = mapped_column(String(64))
    configuration: Mapped[dict[str, object] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_records: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rejected_records: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    report_id: Mapped[str | None] = mapped_column(String(64))

    artifact: Mapped[SourceArtifact] = relationship(back_populates="ingestion_runs")
    created_cases: Mapped[list[FaersCase]] = relationship(
        back_populates="created_by_run", passive_deletes=True
    )
    report_versions: Mapped[list[FaersReportVersion]] = relationship(
        back_populates="ingestion_run", passive_deletes=True
    )
    issues: Mapped[list[IngestionIssue]] = relationship(
        back_populates="ingestion_run", passive_deletes=True
    )
    rejected_rows: Mapped[list[RejectedRecord]] = relationship(
        back_populates="ingestion_run", passive_deletes=True
    )
