"""Quality and reconciliation tests with non-scientific synthetic structures."""

from pathlib import Path

from pharmasense.ingestion.faers.quality import analyze_archive
from pharmasense.ingestion.faers.reporting import write_reports
from pharmasense.ingestion.faers.specification import FaersTable
from tests.unit.ingestion.faers_helpers import blank_record, write_synthetic_archive


def test_quality_report_reconciles_duplicates_and_relationships(tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.zip"
    demo = blank_record(
        FaersTable.DEMO,
        PRIMARYID="1",
        CASEID="1",
        CASEVERSION="1",
        I_F_CODE="I",
        EVENT_DT="202313",
    )
    drug = blank_record(
        FaersTable.DRUG,
        PRIMARYID="1",
        CASEID="1",
        DRUG_SEQ="1",
        ROLE_COD="UNRECOGNIZED",
        DRUGNAME="SYNTHETIC_PRODUCT",
    )
    orphan_therapy = blank_record(FaersTable.THER, PRIMARYID="1", CASEID="1", DSG_DRUG_SEQ="99")
    mismatched_reaction = blank_record(
        FaersTable.REAC, PRIMARYID="1", CASEID="999", PT="SYNTHETIC_TERM"
    )
    write_synthetic_archive(
        archive,
        {
            FaersTable.DEMO: [demo],
            FaersTable.DRUG: [drug, drug],
            FaersTable.REAC: [mismatched_reaction],
            FaersTable.OUTC: [["1", "1"]],
            FaersTable.THER: [orphan_therapy],
        },
    )

    report = analyze_archive(archive)

    assert (
        report.total_source_records == report.total_accepted_records + report.total_rejected_records
    )
    assert report.tables["DRUG"].duplicate_identifier_records == 1
    assert report.tables["DRUG"].duplicate_exact_records == 1
    assert report.tables["DEMO"].invalid_values["EVENT_DT"] == 1
    assert report.tables["DRUG"].invalid_values["ROLE_COD"] == 2
    assert report.tables["OUTC"].rejected_records == 1
    assert report.tables["REAC"].invalid_relationships["CASEID_MISMATCH"] == 1
    assert report.tables["THER"].invalid_relationships["ORPHAN_DRUG_SEQUENCE"] == 1


def test_report_writes_are_idempotent(tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.zip"
    write_synthetic_archive(archive)
    report = analyze_archive(archive)
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"

    assert write_reports(report, json_path, markdown_path) == (True, True)
    first_json = json_path.read_bytes()
    first_markdown = markdown_path.read_bytes()

    assert write_reports(report, json_path, markdown_path) == (False, False)
    assert json_path.read_bytes() == first_json
    assert markdown_path.read_bytes() == first_markdown
