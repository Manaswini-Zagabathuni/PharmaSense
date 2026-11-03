"""Machine-readable contracts for the modern FAERS ASCII extract.

This module deliberately contains no download, database, or row-ingestion behavior. It makes
the Phase 1A parser and relationship design testable before Phase 1B implements the pipeline.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO

FAERS_ASCII_DELIMITER = "$"


class FaersTable(StrEnum):
    """Logical tables in the scoped quarterly ASCII extract."""

    DEMO = "DEMO"
    DRUG = "DRUG"
    REAC = "REAC"
    OUTC = "OUTC"
    THER = "THER"
    INDI = "INDI"


@dataclass(frozen=True)
class FaersTableSpec:
    """Structural requirements used before any row transformation."""

    filename_prefix: str
    required_columns: tuple[str, ...]
    parent: FaersTable | None
    drug_sequence_column: str | None = None


FAERS_TABLE_SPECS: dict[FaersTable, FaersTableSpec] = {
    FaersTable.DEMO: FaersTableSpec("DEMO", ("PRIMARYID", "CASEID"), None),
    FaersTable.DRUG: FaersTableSpec(
        "DRUG", ("PRIMARYID", "CASEID", "DRUG_SEQ", "ROLE_COD", "DRUGNAME"), FaersTable.DEMO
    ),
    FaersTable.REAC: FaersTableSpec("REAC", ("PRIMARYID", "CASEID", "PT"), FaersTable.DEMO),
    FaersTable.OUTC: FaersTableSpec("OUTC", ("PRIMARYID", "CASEID", "OUTC_COD"), FaersTable.DEMO),
    FaersTable.THER: FaersTableSpec(
        "THER",
        ("PRIMARYID", "CASEID", "DSG_DRUG_SEQ"),
        FaersTable.DRUG,
        drug_sequence_column="DSG_DRUG_SEQ",
    ),
    FaersTable.INDI: FaersTableSpec(
        "INDI",
        ("PRIMARYID", "CASEID", "INDI_DRUG_SEQ", "INDI_PT"),
        FaersTable.DRUG,
        drug_sequence_column="INDI_DRUG_SEQ",
    ),
}


def normalize_ascii_header(raw_header: str) -> tuple[str, ...]:
    """Parse a dollar-delimited header and normalize only structural field names."""

    fields = next(csv.reader(StringIO(raw_header), delimiter=FAERS_ASCII_DELIMITER), [])
    return tuple(field.lstrip("\ufeff").strip().upper() for field in fields)


def validate_required_columns(table: FaersTable, columns: Iterable[str]) -> tuple[str, ...]:
    """Return required columns absent from a parsed header, in contract order."""

    observed = {column.strip().upper() for column in columns}
    return tuple(
        column for column in FAERS_TABLE_SPECS[table].required_columns if column not in observed
    )
