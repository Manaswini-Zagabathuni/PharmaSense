# Phase 1D verification report

Verified locally on 2026-11-03. Phase 1D implements restartable ingestion, but the official 2023
Q4 archive was not loaded because no live MySQL server was available. This report distinguishes
source validation and synthetic persistence tests from live MySQL verification.

## Implemented behavior

- Validates the explicit archive filename, byte length, period, safe member structure, and SHA-256
  against the committed source manifest before database mutation.
- Registers one immutable artifact, six source members, and one deterministic ingestion run.
- Loads DEMO, DRUG, REAC, OUTC, THER, and INDI in dependency order and configurable transactions.
- Commits source rows, rejected rows, issues, counters, and the last source-row checkpoint in the
  same transaction.
- Resumes PAUSED, FAILED, or interrupted runs and makes a completed rerun a no-op.
- Preserves exact duplicate child rows by source member/row and supports repeated DRUG sequence
  rows without duplicating the sequence group.
- Produces ignored JSON and Markdown reconciliation reports with source, insertion, skip,
  rejection, database-count, parent, integrity, batch, checksum, duration, and status fields.

## Actual FDA archive validation

Command:

```bash
.venv/bin/python -m pharmasense.ingestion.faers.ingest_cli \
  data/raw/faers/2023Q4/faers_ascii_2023Q4.zip \
  --manifest docs/data-sources/manifests/faers-2023q4-ascii.json \
  --year 2023 --quarter 4 \
  --json-report /tmp/pharmasense-phase1d-validation.json \
  --markdown-report /tmp/pharmasense-phase1d-validation.md \
  --validate-only
```

Actual result:

```text
status=VALIDATED source_rows=5912989 accepted=5912989 rejected=0
```

The observed SHA-256 was
`7e6b72848ed670900eaf78d24983c845f077091f71ffa7b9c310d590faebac62`, matching the committed
manifest. The validation report remained outside Git. Validation does not mean the reports are
causal, complete, deduplicated patient events, or suitable for incidence calculations.

## Automated verification

Focused command:

```bash
.venv/bin/pytest -q \
  tests/unit/ingestion/test_faers_persistence.py \
  tests/unit/ingestion/test_faers_ingest_cli.py \
  tests/integration/ingestion/test_faers_database_ingestion.py
```

Actual result: 10 passed, 1 skipped. The skip requires `TEST_DATABASE_URL`.

The synthetic-only persistence tests verify:

- provenance and report/drug relationships;
- repeated DRUG sequence rows and exact duplicate child rows;
- completed-run idempotency;
- conflicting immutable report-version protection;
- pause and resume from a committed row checkpoint;
- failed-batch rollback followed by resume;
- malformed-row and missing-parent quarantine;
- missing archive members and checksum mismatch;
- unavailable database failure;
- report reconciliation and atomic report writes.

Full command:

```bash
PATH=.venv/bin:/Users/manaswinizagabathuni/.cache/codex-runtimes/\
codex-primary-runtime/dependencies/node/bin:$PATH make check
```

Actual result:

- Ruff lint and formatting: passed; 53 files formatted.
- Strict mypy: passed; 50 source files.
- Backend: 40 passed, 2 skipped in 167.97 seconds; 94.06% coverage.
- Official-archive Phase 1B regression: passed.
- Frontend: 5 passed; 100% statement, branch, function, and line coverage.
- Skips: both live database tests because `TEST_DATABASE_URL` was not configured.

## MySQL blocker

The following checks found no usable local database runtime:

```bash
command -v docker
command -v mysql
command -v mysqld
test -d /Applications/Docker.app
docker --version
mysql --version
```

Actual result: Docker, Docker Desktop, MySQL client, and MySQL server were unavailable. Therefore:

- migration `20261103_0002` was not newly executed against live MySQL 8.4 in this phase;
- the official archive was not loaded into MySQL;
- no production database reconciliation report was generated;
- parser validation and SQLite-backed synthetic persistence tests are not represented as live
  MySQL success.

CI retains a MySQL 8.4 service. The new guarded integration test verifies migration presence,
restartable insertion, repeated DRUG sequence behavior, and completed-rerun idempotency when that
service runs.

## Operational limitation

Checkpoints currently live in `ingestion_run.configuration`, which is appropriate for the single
supported quarter and one ingestion writer. Concurrent writers for the same archive are not
supported; future parallel loading requires explicit database work claiming. If connectivity is
lost after a prior batch committed, that batch remains consistent; updating the run to FAILED may
also be impossible until connectivity returns, so the next invocation treats RUNNING as resumable.
