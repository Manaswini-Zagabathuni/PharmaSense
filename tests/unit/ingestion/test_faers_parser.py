"""Streaming-parser tests with explicitly synthetic structural rows."""

from pathlib import Path

import pytest

from pharmasense.ingestion.faers.archive import inspect_archive
from pharmasense.ingestion.faers.parser import (
    HeaderValidationError,
    IssueCode,
    RejectedRecord,
    SourceRecord,
    iter_table_records,
)
from pharmasense.ingestion.faers.specification import FAERS_TABLE_SPECS, FaersTable
from tests.unit.ingestion.faers_helpers import blank_record, write_synthetic_archive


def test_parser_preserves_values_role_sequence_filename_and_row_number(tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.zip"
    row = blank_record(
        FaersTable.DRUG,
        PRIMARYID="1",
        CASEID="1",
        DRUG_SEQ="7",
        ROLE_COD="SS",
        DRUGNAME="  SYNTHETIC PRODUCT  ",
    )
    write_synthetic_archive(archive, {FaersTable.DRUG: [row]})

    _, records = iter_table_records(archive, FaersTable.DRUG)
    record = next(records)

    assert isinstance(record, SourceRecord)
    assert record.source_filename == "ASCII/DRUG23Q4.txt"
    assert record.source_row_number == 2
    assert record.as_dict()["ROLE_COD"] == "SS"
    assert record.as_dict()["DRUG_SEQ"] == "7"
    assert record.as_dict()["DRUGNAME"] == "  SYNTHETIC PRODUCT  "


def test_parser_emits_stable_rejections_without_silent_drops(tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.zip"
    missing_id = blank_record(FaersTable.DEMO, CASEID="1", CASEVERSION="1")
    malformed = ["2", "2"]
    invalid_identifier = blank_record(
        FaersTable.DEMO, PRIMARYID="not-numeric", CASEID="3", CASEVERSION="1"
    )
    write_synthetic_archive(archive, {FaersTable.DEMO: [missing_id, malformed, invalid_identifier]})

    _, events = iter_table_records(archive, FaersTable.DEMO)
    parsed = list(events)

    assert len(parsed) == 3
    assert all(isinstance(event, RejectedRecord) for event in parsed)
    assert [event.issue_code for event in parsed if isinstance(event, RejectedRecord)] == [
        IssueCode.MISSING_REQUIRED_VALUE,
        IssueCode.ROW_FIELD_COUNT_MISMATCH,
        IssueCode.INVALID_IDENTIFIER,
    ]


def test_parser_rejects_non_ascii_bytes_but_continues(tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.zip"
    values = blank_record(FaersTable.REAC, PRIMARYID="1", CASEID="1", PT="SYNTHETIC_TERM")
    invalid = "$".join(values).encode("ascii") + b"\xff\n"
    write_synthetic_archive(archive, {FaersTable.REAC: [invalid]})

    _, events = iter_table_records(archive, FaersTable.REAC)
    event = next(events)

    assert isinstance(event, RejectedRecord)
    assert event.issue_code in {IssueCode.INVALID_ENCODING, IssueCode.ROW_FIELD_COUNT_MISMATCH}


def test_header_drift_blocks_records(tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.zip"
    wrong_header = (*FAERS_TABLE_SPECS[FaersTable.OUTC].columns, "UNEXPECTED")
    write_synthetic_archive(archive, header_overrides={FaersTable.OUTC: wrong_header})

    _, records = iter_table_records(archive, FaersTable.OUTC)

    with pytest.raises(HeaderValidationError, match=IssueCode.HEADER_MISMATCH):
        next(records)


def test_parser_is_repeatable_and_archive_period_is_verified(tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.zip"
    write_synthetic_archive(archive)

    inspection = inspect_archive(archive)
    _, first = iter_table_records(archive, FaersTable.DEMO, inspection=inspection)
    _, second = iter_table_records(archive, FaersTable.DEMO, inspection=inspection)

    assert inspection.year == 2023
    assert inspection.quarter == 4
    assert list(first) == list(second)
