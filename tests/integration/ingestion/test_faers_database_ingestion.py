"""Live-database ingestion verification, guarded by TEST_DATABASE_URL."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

from pharmasense.db.models import FaersDrug, FaersDrugSequence, IngestionRun
from pharmasense.ingestion.faers.persistence import IngestionStatus, ingest_archive
from pharmasense.ingestion.faers.specification import FaersTable
from tests.unit.ingestion.faers_helpers import (
    blank_record,
    write_synthetic_archive,
    write_synthetic_manifest,
)


@pytest.mark.integration
def test_live_database_restartable_ingestion(tmp_path: Path) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")
    archive = tmp_path / "synthetic-live-database.zip"
    manifest = tmp_path / "manifest.json"
    repeated_drugs: list[list[str] | bytes] = [
        blank_record(
            FaersTable.DRUG,
            PRIMARYID="9000000000001",
            CASEID="900000000000",
            DRUG_SEQ="1",
            ROLE_COD="PS",
            DRUGNAME="SYNTHETIC_INTEGRATION_PRODUCT",
        ),
        blank_record(
            FaersTable.DRUG,
            PRIMARYID="9000000000001",
            CASEID="900000000000",
            DRUG_SEQ="1",
            ROLE_COD="PS",
            DRUGNAME="SYNTHETIC_INTEGRATION_PRODUCT",
            DOSE_VBM="SYNTHETIC_SECOND_DETAIL",
        ),
    ]
    write_synthetic_archive(
        archive,
        {
            FaersTable.DEMO: [
                blank_record(
                    FaersTable.DEMO,
                    PRIMARYID="9000000000001",
                    CASEID="900000000000",
                    CASEVERSION="1",
                )
            ],
            FaersTable.DRUG: repeated_drugs,
            FaersTable.REAC: [],
        },
    )
    write_synthetic_manifest(
        manifest,
        archive,
        {FaersTable.DEMO: 1, FaersTable.DRUG: 2},
    )
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        first = ingest_archive(engine, archive, manifest, year=2023, quarter=4, batch_size=1)
        second = ingest_archive(engine, archive, manifest, year=2023, quarter=4, batch_size=1)
        assert first.status == IngestionStatus.COMPLETED
        assert second.no_op is True
        with engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(FaersDrugSequence)) == 1
            assert connection.scalar(select(func.count()).select_from(FaersDrug)) == 2
            assert connection.scalar(select(func.count()).select_from(IngestionRun)) == 1
    finally:
        engine.dispose()
