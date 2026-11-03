"""Archive safety tests with local synthetic ZIP files."""

import zipfile
from pathlib import Path

import pytest

from pharmasense.ingestion.faers.archive import ArchiveValidationError, inspect_archive


def test_archive_requires_all_scoped_members(tmp_path: Path) -> None:
    archive = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("ASCII/DEMO23Q4.txt", "primaryid$caseid\n")

    with pytest.raises(ArchiveValidationError, match="missing required table members"):
        inspect_archive(archive)


def test_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../DEMO23Q4.txt", "unsafe")

    with pytest.raises(ArchiveValidationError, match="unsafe archive path"):
        inspect_archive(archive)
