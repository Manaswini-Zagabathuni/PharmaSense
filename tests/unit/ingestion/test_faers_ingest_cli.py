"""CLI tests for explicit FAERS validation and database configuration handling."""

import sys
from pathlib import Path

import pytest

from pharmasense.config.settings import get_settings
from pharmasense.ingestion.faers.ingest_cli import main
from pharmasense.ingestion.faers.specification import FaersTable
from tests.unit.ingestion.faers_helpers import (
    write_synthetic_archive,
    write_synthetic_manifest,
)


def test_validate_only_streams_archive_without_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    archive = tmp_path / "synthetic.zip"
    manifest = tmp_path / "manifest.json"
    json_report = tmp_path / "quality.json"
    markdown_report = tmp_path / "quality.md"
    write_synthetic_archive(archive)
    write_synthetic_manifest(
        manifest,
        archive,
        {FaersTable.DEMO: 1, FaersTable.DRUG: 1, FaersTable.REAC: 1},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pharmasense-faers-ingest",
            str(archive),
            "--manifest",
            str(manifest),
            "--year",
            "2023",
            "--quarter",
            "4",
            "--json-report",
            str(json_report),
            "--markdown-report",
            str(markdown_report),
            "--validate-only",
        ],
    )

    assert main() == 0
    assert "status=VALIDATED source_rows=3 accepted=3 rejected=0" in capsys.readouterr().out
    assert json_report.is_file()
    assert markdown_report.is_file()


def test_ingestion_requires_database_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "synthetic.zip"
    manifest = tmp_path / "manifest.json"
    write_synthetic_archive(archive)
    write_synthetic_manifest(manifest, archive, {})
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MYSQL_HOST", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pharmasense-faers-ingest",
            str(archive),
            "--manifest",
            str(manifest),
            "--year",
            "2023",
            "--quarter",
            "4",
            "--json-report",
            str(tmp_path / "report.json"),
            "--markdown-report",
            str(tmp_path / "report.md"),
        ],
    )

    with pytest.raises(SystemExit, match="database configuration"):
        main()
    get_settings.cache_clear()
