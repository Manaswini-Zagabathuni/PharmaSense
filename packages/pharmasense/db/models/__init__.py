"""Relational model registry imported by Alembic and application services."""

from pharmasense.db.models.faers import (
    FaersCase,
    FaersDrug,
    FaersDrugSequence,
    FaersIndication,
    FaersOutcome,
    FaersReaction,
    FaersReportVersion,
    FaersTherapy,
)
from pharmasense.db.models.provenance import IngestionRun, SourceArtifact, SourceMember
from pharmasense.db.models.quality import IngestionIssue, RejectedRecord

__all__ = [
    "FaersCase",
    "FaersDrug",
    "FaersDrugSequence",
    "FaersIndication",
    "FaersOutcome",
    "FaersReaction",
    "FaersReportVersion",
    "FaersTherapy",
    "IngestionIssue",
    "IngestionRun",
    "RejectedRecord",
    "SourceArtifact",
    "SourceMember",
]
