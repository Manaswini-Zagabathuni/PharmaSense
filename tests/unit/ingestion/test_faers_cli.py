"""CLI wiring tests using a tiny non-scientific synthetic archive."""

import sys
from pathlib import Path

import pytest

from pharmasense.ingestion.faers.cli import main
from tests.unit.ingestion.faers_helpers import write_synthetic_archive


def test_cli_writes_reports_and_reports_idempotent_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    archive = tmp_path / "synthetic.zip"
    json_report = tmp_path / "quality.json"
    markdown_report = tmp_path / "quality.md"
    write_synthetic_archive(archive)
    arguments = [
        "pharmasense-faers-inspect",
        str(archive),
        "--json-report",
        str(json_report),
        "--markdown-report",
        str(markdown_report),
    ]

    monkeypatch.setattr(sys, "argv", arguments)
    assert main() == 0
    first_output = capsys.readouterr().out
    assert "json_changed=True" in first_output
    assert json_report.is_file()
    assert markdown_report.is_file()

    assert main() == 0
    second_output = capsys.readouterr().out
    assert "json_changed=False" in second_output
    assert "markdown_changed=False" in second_output
