"""Opt-in checks against the ignored, official FDA 2023 Q4 archive."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pharmasense.ingestion.faers.archive import inspect_archive, sha256_file
from pharmasense.ingestion.faers.parser import SourceRecord, iter_table_records
from pharmasense.ingestion.faers.quality import analyze_archive
from pharmasense.ingestion.faers.specification import FAERS_TABLE_SPECS, FaersTable

EXPECTED_SHA256 = "7e6b72848ed670900eaf78d24983c845f077091f71ffa7b9c310d590faebac62"
EXPECTED_ROWS = {
    "DEMO": 415_379,
    "DRUG": 1_920_732,
    "REAC": 1_500_033,
    "OUTC": 327_797,
    "THER": 633_087,
    "INDI": 1_115_961,
}
DEFAULT_ARCHIVE = Path("data/raw/faers/2023Q4/faers_ascii_2023Q4.zip")
ARCHIVE = Path(os.environ.get("FAERS_2023Q4_ARCHIVE", DEFAULT_ARCHIVE))

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not ARCHIVE.is_file(), reason="official 2023 Q4 archive is not available"),
]


def test_official_archive_identity_headers_samples_and_full_reconciliation() -> None:
    assert sha256_file(ARCHIVE) == EXPECTED_SHA256
    inspection = inspect_archive(ARCHIVE)
    assert (inspection.year, inspection.quarter) == (2023, 4)

    for table in FaersTable:
        columns, records = iter_table_records(ARCHIVE, table, inspection=inspection)
        first_record = next(records)
        assert columns == FAERS_TABLE_SPECS[table].columns
        assert isinstance(first_record, SourceRecord)
        assert first_record.source_row_number == 2

    report = analyze_archive(ARCHIVE)

    assert report.archive_sha256 == EXPECTED_SHA256
    assert report.total_source_records == sum(EXPECTED_ROWS.values())
    assert report.total_accepted_records == report.total_source_records
    assert report.total_rejected_records == 0
    assert {name: table.source_records for name, table in report.tables.items()} == EXPECTED_ROWS
    assert all(
        count == 0
        for table in report.tables.values()
        for count in table.invalid_relationships.values()
    )
