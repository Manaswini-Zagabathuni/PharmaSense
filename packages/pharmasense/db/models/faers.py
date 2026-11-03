"""Normalized, lossless FAERS report and child-table models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pharmasense.db.base import Base
from pharmasense.db.models.common import CreatedAtMixin, source_identifier

if TYPE_CHECKING:
    from pharmasense.db.models.provenance import IngestionRun, SourceMember


class SourceRowMixin(CreatedAtMixin):
    """Provenance shared by every immutable FDA source row."""

    source_member_id: Mapped[int] = mapped_column(
        ForeignKey("source_member.id", ondelete="RESTRICT"), nullable=False
    )
    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_run.id", ondelete="RESTRICT"), nullable=False
    )
    source_row_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_extras: Mapped[dict[str, object] | None] = mapped_column(JSON)


class FaersCase(CreatedAtMixin, Base):
    """Longitudinal FDA case keyed by the original CASEID string."""

    __tablename__ = "faers_case"

    case_id: Mapped[str] = mapped_column(source_identifier(500), primary_key=True)
    created_by_run_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_run.id", ondelete="RESTRICT"), nullable=False
    )

    created_by_run: Mapped[IngestionRun] = relationship(back_populates="created_cases")
    report_versions: Mapped[list[FaersReportVersion]] = relationship(
        back_populates="case", passive_deletes=True, order_by="FaersReportVersion.case_version"
    )


class FaersReportVersion(SourceRowMixin, Base):
    """One immutable DEMO report version identified by PRIMARYID."""

    __tablename__ = "faers_report_version"
    __table_args__ = (
        UniqueConstraint("case_id", "case_version"),
        UniqueConstraint("source_member_id", "source_row_number"),
        CheckConstraint("source_quarter BETWEEN 1 AND 4", name="source_quarter_range"),
        Index("ix_faers_report_version_case", "case_id", "case_version"),
        Index("ix_faers_report_version_period", "source_year", "source_quarter"),
        Index("ix_faers_report_version_fda_date", "fda_dt"),
    )

    primary_id: Mapped[str] = mapped_column(source_identifier(1000), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        source_identifier(500),
        ForeignKey("faers_case.case_id", ondelete="RESTRICT"),
        nullable=False,
    )
    case_version: Mapped[str] = mapped_column(source_identifier(10), nullable=False)
    source_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source_quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    i_f_code: Mapped[str | None] = mapped_column(String(8))
    event_dt: Mapped[str | None] = mapped_column(String(8))
    mfr_dt: Mapped[str | None] = mapped_column(String(8))
    init_fda_dt: Mapped[str | None] = mapped_column(String(8))
    fda_dt: Mapped[str | None] = mapped_column(String(8))
    rept_cod: Mapped[str | None] = mapped_column(String(16))
    auth_num: Mapped[str | None] = mapped_column(Text)
    mfr_num: Mapped[str | None] = mapped_column(Text)
    mfr_sndr: Mapped[str | None] = mapped_column(Text)
    lit_ref: Mapped[str | None] = mapped_column(Text)
    age: Mapped[str | None] = mapped_column(String(32))
    age_cod: Mapped[str | None] = mapped_column(String(16))
    age_grp: Mapped[str | None] = mapped_column(String(16))
    sex: Mapped[str | None] = mapped_column(String(8))
    e_sub: Mapped[str | None] = mapped_column(String(8))
    wt: Mapped[str | None] = mapped_column(String(32))
    wt_cod: Mapped[str | None] = mapped_column(String(20))
    rept_dt: Mapped[str | None] = mapped_column(String(8))
    to_mfr: Mapped[str | None] = mapped_column(String(100))
    occp_cod: Mapped[str | None] = mapped_column(String(300))
    reporter_country: Mapped[str | None] = mapped_column(String(500))
    occr_country: Mapped[str | None] = mapped_column(String(8))

    case: Mapped[FaersCase] = relationship(back_populates="report_versions")
    source_member: Mapped[SourceMember] = relationship()
    ingestion_run: Mapped[IngestionRun] = relationship(back_populates="report_versions")
    drug_sequences: Mapped[list[FaersDrugSequence]] = relationship(
        back_populates="report_version", passive_deletes=True
    )
    reactions: Mapped[list[FaersReaction]] = relationship(
        back_populates="report_version", passive_deletes=True
    )
    outcomes: Mapped[list[FaersOutcome]] = relationship(
        back_populates="report_version", passive_deletes=True
    )


class FaersDrugSequence(CreatedAtMixin, Base):
    """Relationship group for all DRUG details sharing a sequence number."""

    __tablename__ = "faers_drug_sequence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["primary_id"], ["faers_report_version.primary_id"], ondelete="RESTRICT"
        ),
        CheckConstraint("source_quarter BETWEEN 1 AND 4", name="source_quarter_range"),
        Index("ix_faers_drug_sequence_period", "source_year", "source_quarter"),
    )

    primary_id: Mapped[str] = mapped_column(source_identifier(1000), primary_key=True)
    drug_seq: Mapped[str] = mapped_column(source_identifier(10), primary_key=True)
    source_member_id: Mapped[int] = mapped_column(
        ForeignKey("source_member.id", ondelete="RESTRICT"), nullable=False
    )
    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_run.id", ondelete="RESTRICT"), nullable=False
    )
    source_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source_quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    report_version: Mapped[FaersReportVersion] = relationship(back_populates="drug_sequences")
    source_member: Mapped[SourceMember] = relationship()
    ingestion_run: Mapped[IngestionRun] = relationship()
    drugs: Mapped[list[FaersDrug]] = relationship(
        back_populates="drug_sequence", passive_deletes=True
    )
    therapies: Mapped[list[FaersTherapy]] = relationship(
        back_populates="drug_sequence", passive_deletes=True
    )
    indications: Mapped[list[FaersIndication]] = relationship(
        back_populates="drug_sequence", passive_deletes=True
    )


class FaersDrug(SourceRowMixin, Base):
    """One source DRUG row; repeated report/sequence pairs are preserved."""

    __tablename__ = "faers_drug"
    __table_args__ = (
        ForeignKeyConstraint(
            ["primary_id", "drug_seq"],
            ["faers_drug_sequence.primary_id", "faers_drug_sequence.drug_seq"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("source_member_id", "source_row_number"),
        Index("ix_faers_drug_report_role", "primary_id", "role_cod"),
        Index("ix_faers_drug_name", "drugname", mysql_length=191),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    primary_id: Mapped[str] = mapped_column(source_identifier(1000), nullable=False)
    source_case_id: Mapped[str] = mapped_column(source_identifier(500), nullable=False)
    drug_seq: Mapped[str] = mapped_column(source_identifier(10), nullable=False)
    role_cod: Mapped[str] = mapped_column(String(22), nullable=False)
    drugname: Mapped[str] = mapped_column(Text, nullable=False)
    prod_ai: Mapped[str | None] = mapped_column(Text)
    val_vbm: Mapped[str | None] = mapped_column(String(22))
    route: Mapped[str | None] = mapped_column(Text)
    dose_vbm: Mapped[str | None] = mapped_column(Text)
    cum_dose_chr: Mapped[str | None] = mapped_column(String(32))
    cum_dose_unit: Mapped[str | None] = mapped_column(String(64))
    dechal: Mapped[str | None] = mapped_column(String(20))
    rechal: Mapped[str | None] = mapped_column(String(20))
    lot_num: Mapped[str | None] = mapped_column(Text)
    exp_dt: Mapped[str | None] = mapped_column(Text)
    nda_num: Mapped[str | None] = mapped_column(String(100))
    dose_amt: Mapped[str | None] = mapped_column(String(32))
    dose_unit: Mapped[str | None] = mapped_column(String(64))
    dose_form: Mapped[str | None] = mapped_column(String(64))
    dose_freq: Mapped[str | None] = mapped_column(String(64))

    drug_sequence: Mapped[FaersDrugSequence] = relationship(back_populates="drugs")
    source_member: Mapped[SourceMember] = relationship()
    ingestion_run: Mapped[IngestionRun] = relationship()


class FaersReaction(SourceRowMixin, Base):
    """One report-level REAC source row."""

    __tablename__ = "faers_reaction"
    __table_args__ = (
        UniqueConstraint("source_member_id", "source_row_number"),
        Index("ix_faers_reaction_report", "primary_id"),
        Index("ix_faers_reaction_term", "pt", mysql_length=191),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    primary_id: Mapped[str] = mapped_column(
        source_identifier(1000),
        ForeignKey("faers_report_version.primary_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_case_id: Mapped[str] = mapped_column(source_identifier(500), nullable=False)
    pt: Mapped[str] = mapped_column(Text, nullable=False)
    drug_rec_act: Mapped[str | None] = mapped_column(Text)

    report_version: Mapped[FaersReportVersion] = relationship(back_populates="reactions")
    source_member: Mapped[SourceMember] = relationship()
    ingestion_run: Mapped[IngestionRun] = relationship()


class FaersOutcome(SourceRowMixin, Base):
    """One report-level OUTC source row."""

    __tablename__ = "faers_outcome"
    __table_args__ = (
        UniqueConstraint("source_member_id", "source_row_number"),
        Index("ix_faers_outcome_report_code", "primary_id", "outc_cod"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    primary_id: Mapped[str] = mapped_column(
        source_identifier(1000),
        ForeignKey("faers_report_version.primary_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_case_id: Mapped[str] = mapped_column(source_identifier(500), nullable=False)
    outc_cod: Mapped[str] = mapped_column(String(32), nullable=False)

    report_version: Mapped[FaersReportVersion] = relationship(back_populates="outcomes")
    source_member: Mapped[SourceMember] = relationship()
    ingestion_run: Mapped[IngestionRun] = relationship()


class FaersTherapy(SourceRowMixin, Base):
    """One THER interval linked to a report-level drug sequence."""

    __tablename__ = "faers_therapy"
    __table_args__ = (
        ForeignKeyConstraint(
            ["primary_id", "drug_seq"],
            ["faers_drug_sequence.primary_id", "faers_drug_sequence.drug_seq"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("source_member_id", "source_row_number"),
        Index("ix_faers_therapy_drug_sequence", "primary_id", "drug_seq"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    primary_id: Mapped[str] = mapped_column(source_identifier(1000), nullable=False)
    source_case_id: Mapped[str] = mapped_column(source_identifier(500), nullable=False)
    drug_seq: Mapped[str] = mapped_column(source_identifier(10), nullable=False)
    start_dt: Mapped[str | None] = mapped_column(String(8))
    end_dt: Mapped[str | None] = mapped_column(String(8))
    dur: Mapped[str | None] = mapped_column(Text)
    dur_cod: Mapped[str | None] = mapped_column(Text)

    drug_sequence: Mapped[FaersDrugSequence] = relationship(back_populates="therapies")
    source_member: Mapped[SourceMember] = relationship()
    ingestion_run: Mapped[IngestionRun] = relationship()


class FaersIndication(SourceRowMixin, Base):
    """One INDI term linked to a report-level drug sequence."""

    __tablename__ = "faers_indication"
    __table_args__ = (
        ForeignKeyConstraint(
            ["primary_id", "drug_seq"],
            ["faers_drug_sequence.primary_id", "faers_drug_sequence.drug_seq"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("source_member_id", "source_row_number"),
        Index("ix_faers_indication_drug_sequence", "primary_id", "drug_seq"),
        Index("ix_faers_indication_term", "indi_pt", mysql_length=191),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    primary_id: Mapped[str] = mapped_column(source_identifier(1000), nullable=False)
    source_case_id: Mapped[str] = mapped_column(source_identifier(500), nullable=False)
    drug_seq: Mapped[str] = mapped_column(source_identifier(10), nullable=False)
    indi_pt: Mapped[str] = mapped_column(Text, nullable=False)

    drug_sequence: Mapped[FaersDrugSequence] = relationship(back_populates="indications")
    source_member: Mapped[SourceMember] = relationship()
    ingestion_run: Mapped[IngestionRun] = relationship()
