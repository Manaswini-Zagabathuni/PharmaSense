"""Deterministic JSON and Markdown reporting for FAERS archive inspection."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pharmasense.ingestion.faers.quality import QualityReport


def render_markdown(report: QualityReport) -> str:
    """Render a human-readable summary without raw report content."""

    lines = [
        "# FAERS 2023 Q4 ASCII parsing report",
        "",
        "> These are structural parsing and data-quality observations, not clinical findings.",
        "> Report counts do not establish causality, incidence, or comparative safety.",
        "",
        "## Source",
        "",
        f"- Archive: `{report.archive_filename}`",
        f"- Bytes: {report.archive_bytes:,}",
        f"- SHA-256: `{report.archive_sha256}`",
        f"- Parser version: `{report.parser_version}`",
        f"- Deterministic report ID: `{report.report_id}`",
        "",
        "## Reconciliation",
        "",
        "| Table | Bytes | Columns | Source rows | Accepted | Rejected | Duplicate IDs | "
        "Exact duplicates | Invalid relationships |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for table_name, table in report.tables.items():
        invalid_relationships = sum(table.invalid_relationships.values())
        lines.append(
            f"| {table_name} | {table.source_bytes:,} | {len(table.columns)} | "
            f"{table.source_records:,} | {table.accepted_records:,} | "
            f"{table.rejected_records:,} | {table.duplicate_identifier_records:,} | "
            f"{table.duplicate_exact_records:,} | {invalid_relationships:,} |"
        )
    lines.extend(
        [
            "",
            f"Total source rows: **{report.total_source_records:,}**  ",
            f"Accepted structural rows: **{report.total_accepted_records:,}**  ",
            f"Rejected structural rows: **{report.total_rejected_records:,}**",
            "",
            "For each table, `source rows = accepted + rejected`. Invalid relationships are "
            "reported separately and are not silently removed from the parser stream.",
            "",
            "## Headers, missing values, and issues",
            "",
        ]
    )
    for table_name, table in report.tables.items():
        missing = {name: count for name, count in table.missing_values.items() if count}
        lines.extend(
            [
                f"### {table_name}",
                "",
                f"Member: `{table.source_filename}`",
                "",
                f"Header ({len(table.columns)} columns): `{' | '.join(table.columns)}`",
                "",
                f"Missing values: `{json.dumps(missing, sort_keys=True)}`",
                "",
                f"Invalid values: `{json.dumps(table.invalid_values, sort_keys=True)}`",
                "",
                f"Issues/warnings: `{json.dumps(table.issue_counts, sort_keys=True)}`",
                "",
                "Invalid relationships: "
                f"`{json.dumps(table.invalid_relationships, sort_keys=True)}`",
                "",
            ]
        )
    return "\n".join(lines)


def _write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        Path(temporary_name).replace(path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return True


def write_reports(report: QualityReport, json_path: Path, markdown_path: Path) -> tuple[bool, bool]:
    """Atomically write reports; identical reruns do not modify existing files."""

    json_content = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
    markdown_content = render_markdown(report) + "\n"
    return (
        _write_if_changed(json_path, json_content),
        _write_if_changed(markdown_path, markdown_content),
    )
