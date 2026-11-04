"""Command-line entry point for restartable FAERS database ingestion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pharmasense.config.settings import get_settings
from pharmasense.db.engine import build_engine
from pharmasense.ingestion.faers.persistence import (
    DEFAULT_BATCH_SIZE,
    ingest_archive,
    write_reconciliation_reports,
)
from pharmasense.ingestion.faers.quality import analyze_archive
from pharmasense.ingestion.faers.reporting import write_reports


def build_parser() -> argparse.ArgumentParser:
    """Build the explicit-source ingestion CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--quarter", required=True, type=int, choices=range(1, 5))
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--json-report", required=True, type=Path)
    parser.add_argument("--markdown-report", required=True, type=Path)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="stream and validate the archive without connecting to the database",
    )
    return parser


def main() -> int:
    """Validate or ingest an explicitly selected FAERS archive."""

    arguments = build_parser().parse_args()
    if arguments.validate_only:
        quality = analyze_archive(arguments.archive)
        if (quality.source_year, quality.source_quarter) != (arguments.year, arguments.quarter):
            raise SystemExit("archive period does not match --year/--quarter")
        manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
        if quality.archive_sha256 != manifest["archive_sha256"]:
            raise SystemExit("archive checksum does not match manifest")
        write_reports(quality, arguments.json_report, arguments.markdown_report)
        print(
            f"status=VALIDATED source_rows={quality.total_source_records} "
            f"accepted={quality.total_accepted_records} rejected={quality.total_rejected_records}"
        )
        return 0

    database_url = get_settings().sqlalchemy_url()
    if database_url is None:
        raise SystemExit("database configuration is required for ingestion")
    engine = build_engine(database_url)
    try:
        report = ingest_archive(
            engine,
            arguments.archive,
            arguments.manifest,
            year=arguments.year,
            quarter=arguments.quarter,
            batch_size=arguments.batch_size,
            max_batches=arguments.max_batches,
        )
    finally:
        engine.dispose()
    write_reconciliation_reports(report, arguments.json_report, arguments.markdown_report)
    total_inserted = sum(item.inserted_rows for item in report.tables.values())
    total_rejected = sum(item.rejected_rows for item in report.tables.values())
    print(
        f"status={report.status} run_id={report.run_id} inserted={total_inserted} "
        f"rejected={total_rejected} no_op={str(report.no_op).lower()} "
        f"elapsed_seconds={report.duration_seconds:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
