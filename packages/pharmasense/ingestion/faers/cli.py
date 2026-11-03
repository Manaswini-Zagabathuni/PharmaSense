"""Command-line entry point for bounded FAERS archive inspection."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from pharmasense.ingestion.faers.quality import analyze_archive
from pharmasense.ingestion.faers.reporting import write_reports


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser independently for testability."""

    parser = argparse.ArgumentParser(description="Inspect one local FAERS ASCII quarterly ZIP")
    parser.add_argument("archive", type=Path, help="path to the preserved FDA ZIP")
    parser.add_argument("--json-report", required=True, type=Path)
    parser.add_argument("--markdown-report", required=True, type=Path)
    return parser


def main() -> int:
    """Analyze the archive and write deterministic aggregate reports."""

    arguments = build_parser().parse_args()
    started = time.perf_counter()
    report = analyze_archive(arguments.archive)
    json_changed, markdown_changed = write_reports(
        report, arguments.json_report, arguments.markdown_report
    )
    elapsed = time.perf_counter() - started
    print(
        f"parsed={report.total_source_records} accepted={report.total_accepted_records} "
        f"rejected={report.total_rejected_records} elapsed_seconds={elapsed:.3f} "
        f"json_changed={json_changed} markdown_changed={markdown_changed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
