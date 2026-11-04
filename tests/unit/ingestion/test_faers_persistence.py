"""Restartable persistence tests using explicitly synthetic FAERS-shaped records."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, event, func, select
from sqlalchemy.exc import OperationalError

from pharmasense.db.base import Base
from pharmasense.db.models import (
    FaersDrug,
    FaersDrugSequence,
    FaersReaction,
    FaersReportVersion,
    IngestionIssue,
    IngestionRun,
    RejectedRecord,
    SourceArtifact,
    SourceMember,
)
from pharmasense.ingestion.faers import persistence
from pharmasense.ingestion.faers.archive import ArchiveValidationError
from pharmasense.ingestion.faers.persistence import (
    IngestionStatus,
    IngestionValidationError,
    ingest_archive,
    write_reconciliation_reports,
)
from pharmasense.ingestion.faers.specification import FaersTable
from tests.unit.ingestion.faers_helpers import (
    blank_record,
    write_synthetic_archive,
    write_synthetic_manifest,
)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    database = create_engine(f"sqlite:///{tmp_path / 'ingestion.sqlite3'}")

    @event.listens_for(database, "connect")
    def enable_foreign_keys(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(database)
    yield database
    database.dispose()


def build_complete_fixture(tmp_path: Path) -> tuple[Path, Path]:
    archive = tmp_path / "synthetic.zip"
    manifest = tmp_path / "manifest.json"
    overrides: dict[FaersTable, list[list[str] | bytes]] = {
        FaersTable.DRUG: [
            blank_record(
                FaersTable.DRUG,
                PRIMARYID="1",
                CASEID="1",
                DRUG_SEQ="1",
                ROLE_COD="PS",
                DRUGNAME="SYNTHETIC_PRODUCT",
                DOSE_VBM="SYNTHETIC_DOSE_A",
            ),
            blank_record(
                FaersTable.DRUG,
                PRIMARYID="1",
                CASEID="1",
                DRUG_SEQ="1",
                ROLE_COD="PS",
                DRUGNAME="SYNTHETIC_PRODUCT",
                DOSE_VBM="SYNTHETIC_DOSE_B",
            ),
        ],
        FaersTable.REAC: [
            blank_record(
                FaersTable.REAC,
                PRIMARYID="1",
                CASEID="1",
                PT="SYNTHETIC_DUPLICATE_TERM",
            ),
            blank_record(
                FaersTable.REAC,
                PRIMARYID="1",
                CASEID="1",
                PT="SYNTHETIC_DUPLICATE_TERM",
            ),
        ],
        FaersTable.OUTC: [blank_record(FaersTable.OUTC, PRIMARYID="1", CASEID="1", OUTC_COD="OT")],
        FaersTable.THER: [
            blank_record(
                FaersTable.THER,
                PRIMARYID="1",
                CASEID="1",
                DSG_DRUG_SEQ="1",
                START_DT="2023",
            )
        ],
        FaersTable.INDI: [
            blank_record(
                FaersTable.INDI,
                PRIMARYID="1",
                CASEID="1",
                INDI_DRUG_SEQ="1",
                INDI_PT="SYNTHETIC_INDICATION",
            )
        ],
    }
    write_synthetic_archive(archive, overrides)
    write_synthetic_manifest(
        manifest,
        archive,
        {
            FaersTable.DEMO: 1,
            FaersTable.DRUG: 2,
            FaersTable.REAC: 2,
            FaersTable.OUTC: 1,
            FaersTable.THER: 1,
            FaersTable.INDI: 1,
        },
    )
    return archive, manifest


def test_persists_provenance_relationships_and_repeated_drug_sequence(
    engine: Engine, tmp_path: Path
) -> None:
    archive, manifest = build_complete_fixture(tmp_path)

    report = ingest_archive(
        engine,
        archive,
        manifest,
        year=2023,
        quarter=4,
        batch_size=2,
        require_migration=False,
    )

    assert report.status == IngestionStatus.COMPLETED
    assert report.tables["DRUG"].inserted_rows == 2
    assert report.tables["DRUG"].source_rows == 2
    assert not any(report.foreign_key_violations.values())
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(FaersDrugSequence)) == 1
        assert connection.scalar(select(func.count()).select_from(FaersDrug)) == 2
        assert connection.scalar(select(func.count()).select_from(FaersReaction)) == 2
        assert connection.scalar(select(func.count()).select_from(SourceArtifact)) == 1
        assert connection.scalar(select(func.count()).select_from(SourceMember)) == 6
        drug_rows = connection.execute(
            select(FaersDrug.drug_seq, FaersDrug.source_case_id).order_by(FaersDrug.id)
        ).all()
    assert [tuple(row) for row in drug_rows] == [("1", "1"), ("1", "1")]


def test_completed_rerun_is_a_noop(engine: Engine, tmp_path: Path) -> None:
    archive, manifest = build_complete_fixture(tmp_path)
    first = ingest_archive(engine, archive, manifest, year=2023, quarter=4, require_migration=False)
    second = ingest_archive(
        engine, archive, manifest, year=2023, quarter=4, require_migration=False
    )

    assert first.no_op is False
    assert second.no_op is True
    assert second.run_id == first.run_id
    assert second.tables["DEMO"].inserted_rows == 0
    assert second.tables["DRUG"].previously_existing_rows == 2
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(IngestionRun)) == 1
        assert connection.scalar(select(func.count()).select_from(FaersReportVersion)) == 1
        assert connection.scalar(select(func.count()).select_from(FaersDrug)) == 2


def test_conflicting_report_version_never_overwrites_history(
    engine: Engine, tmp_path: Path
) -> None:
    archive, manifest = build_complete_fixture(tmp_path)
    ingest_archive(engine, archive, manifest, year=2023, quarter=4, require_migration=False)
    conflict_archive = tmp_path / "synthetic-conflict.zip"
    conflict_manifest = tmp_path / "conflict-manifest.json"
    write_synthetic_archive(
        conflict_archive,
        {
            FaersTable.DEMO: [
                blank_record(
                    FaersTable.DEMO,
                    PRIMARYID="1",
                    CASEID="1",
                    CASEVERSION="1",
                    I_F_CODE="F",
                )
            ]
        },
    )
    write_synthetic_manifest(
        conflict_manifest,
        conflict_archive,
        {FaersTable.DEMO: 1, FaersTable.DRUG: 1, FaersTable.REAC: 1},
    )

    with pytest.raises(IngestionValidationError, match="conflicts"):
        ingest_archive(
            engine,
            conflict_archive,
            conflict_manifest,
            year=2023,
            quarter=4,
            require_migration=False,
        )

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(FaersReportVersion)) == 1
        statuses = list(connection.scalars(select(IngestionRun.status).order_by(IngestionRun.id)))
    assert statuses == [IngestionStatus.COMPLETED, IngestionStatus.FAILED]


def test_paused_run_resumes_after_committed_checkpoint(engine: Engine, tmp_path: Path) -> None:
    archive, manifest = build_complete_fixture(tmp_path)
    paused = ingest_archive(
        engine,
        archive,
        manifest,
        year=2023,
        quarter=4,
        batch_size=1,
        max_batches=2,
        require_migration=False,
    )
    assert paused.status == IngestionStatus.PAUSED
    assert paused.tables["DEMO"].complete is True
    assert paused.tables["DRUG"].source_rows == 1

    completed = ingest_archive(
        engine,
        archive,
        manifest,
        year=2023,
        quarter=4,
        batch_size=1,
        require_migration=False,
    )
    assert completed.status == IngestionStatus.COMPLETED
    assert completed.resume_count == 1
    assert completed.tables["DRUG"].source_rows == 2
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(FaersDrug)) == 2


def test_failed_batch_rolls_back_and_run_can_resume(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, manifest = build_complete_fixture(tmp_path)
    original = persistence._persist_batch
    calls = 0

    def fail_second_batch(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OperationalError("synthetic statement", {}, RuntimeError("test-only failure"))
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(persistence, "_persist_batch", fail_second_batch)
    with pytest.raises(OperationalError, match="test-only failure"):
        ingest_archive(
            engine,
            archive,
            manifest,
            year=2023,
            quarter=4,
            batch_size=1,
            require_migration=False,
        )

    with engine.connect() as connection:
        assert connection.scalar(select(IngestionRun.status)) == IngestionStatus.FAILED
        assert connection.scalar(select(func.count()).select_from(FaersReportVersion)) == 1
        assert connection.scalar(select(func.count()).select_from(FaersDrug)) == 0

    monkeypatch.setattr(persistence, "_persist_batch", original)
    completed = ingest_archive(
        engine,
        archive,
        manifest,
        year=2023,
        quarter=4,
        batch_size=1,
        require_migration=False,
    )
    assert completed.status == IngestionStatus.COMPLETED
    assert completed.resume_count == 1
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(FaersDrug)) == 2


def test_malformed_and_orphan_rows_are_quarantined(engine: Engine, tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.zip"
    manifest = tmp_path / "manifest.json"
    orphan = blank_record(
        FaersTable.DRUG,
        PRIMARYID="999",
        CASEID="999",
        DRUG_SEQ="1",
        ROLE_COD="PS",
        DRUGNAME="SYNTHETIC_ORPHAN",
    )
    malformed = ["1", "1"]
    write_synthetic_archive(
        archive,
        {FaersTable.DRUG: [orphan], FaersTable.REAC: [malformed]},
    )
    write_synthetic_manifest(
        manifest,
        archive,
        {FaersTable.DEMO: 1, FaersTable.DRUG: 1, FaersTable.REAC: 1},
    )

    report = ingest_archive(
        engine, archive, manifest, year=2023, quarter=4, require_migration=False
    )

    assert report.tables["DRUG"].rejected_rows == 1
    assert report.tables["REAC"].rejected_rows == 1
    assert report.missing_parent_references["ORPHAN_REPORT"] == 1
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(RejectedRecord)) == 2
        assert connection.scalar(select(func.count()).select_from(IngestionIssue)) == 2


def test_reports_are_atomic_and_machine_readable(engine: Engine, tmp_path: Path) -> None:
    archive, manifest = build_complete_fixture(tmp_path)
    report = ingest_archive(
        engine, archive, manifest, year=2023, quarter=4, require_migration=False
    )
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"

    write_reconciliation_reports(report, json_path, markdown_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["status"] == "COMPLETED"
    assert payload["tables"]["DEMO"]["source_rows"] == 1
    assert "reporting records, not incidence" in markdown_path.read_text(encoding="utf-8")
    assert not list(tmp_path.glob("*.tmp"))


def test_checksum_missing_member_and_unavailable_database_fail_explicitly(
    engine: Engine, tmp_path: Path
) -> None:
    archive, manifest = build_complete_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["archive_sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(IngestionValidationError, match="SHA-256"):
        ingest_archive(engine, archive, manifest, year=2023, quarter=4, require_migration=False)

    incomplete = tmp_path / "incomplete.zip"
    write_synthetic_archive(incomplete)
    # Create a valid ZIP lacking INDI by rewriting only selected members.
    missing = tmp_path / "missing.zip"
    with zipfile.ZipFile(incomplete) as source, zipfile.ZipFile(missing, "w") as target:
        for item in source.infolist():
            if "INDI" not in item.filename:
                target.writestr(item, source.read(item.filename))
    missing_manifest = tmp_path / "missing-manifest.json"
    write_synthetic_manifest(missing_manifest, missing, {})
    with pytest.raises(ArchiveValidationError, match="INDI"):
        ingest_archive(
            engine,
            missing,
            missing_manifest,
            year=2023,
            quarter=4,
            require_migration=False,
        )

    write_synthetic_manifest(
        manifest,
        archive,
        {
            FaersTable.DEMO: 1,
            FaersTable.DRUG: 2,
            FaersTable.REAC: 2,
            FaersTable.OUTC: 1,
            FaersTable.THER: 1,
            FaersTable.INDI: 1,
        },
    )
    unavailable = create_engine(f"sqlite:///{tmp_path / 'absent' / 'database.sqlite3'}")
    with pytest.raises(OperationalError):
        ingest_archive(
            unavailable,
            archive,
            manifest,
            year=2023,
            quarter=4,
            require_migration=False,
        )
    unavailable.dispose()
