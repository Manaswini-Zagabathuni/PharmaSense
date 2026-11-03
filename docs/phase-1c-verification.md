# Phase 1C verification report

Verified on 2026-11-03 in the local macOS development environment. No FDA records were loaded and
no additional archive was downloaded.

## Source reconciliation

The schema was reviewed against the preserved official 2023 Q4 archive documentation:

- `Readme.pdf`
- `ASC_NTS.pdf` (ASCII field and relationship definitions)
- `FAQs.pdf` (including the repeated `PRIMARYID` + `DRUG_SEQ` clarification)
- the committed Phase 1B archive manifest and verification report

The review confirmed report-version identity, partial date representation, report-level REAC and
OUTC relationships, drug-sequence THER and INDI relationships, and the requirement to retain
multiple DRUG rows for one sequence.

## Commands and actual results

```text
git status --short --branch
git rev-parse HEAD
```

Result before implementation: clean `main` checkout at
`53714efe0e62f92f19e8bb13d94d1b7d983012c7`.

```text
DATABASE_URL=sqlite:////tmp/pharmasense-phase1c-autogen-v3.sqlite3 \
  .venv/bin/alembic upgrade head
DATABASE_URL=sqlite:////tmp/pharmasense-phase1c-autogen-v3.sqlite3 \
  .venv/bin/alembic revision --autogenerate --rev-id 20261103_0002 \
  -m "add FAERS persistence foundation"
```

Result: baseline applied and an additive revision generated from registered model metadata. The
revision was formatted and manually reviewed.

```text
DATABASE_URL=sqlite:////tmp/pharmasense-phase1c-migration-v4.sqlite3 \
  .venv/bin/alembic upgrade head
DATABASE_URL=sqlite:////tmp/pharmasense-phase1c-migration-v4.sqlite3 \
  .venv/bin/alembic current
DATABASE_URL=sqlite:////tmp/pharmasense-phase1c-migration-v4.sqlite3 \
  .venv/bin/alembic check
DATABASE_URL=sqlite:////tmp/pharmasense-phase1c-migration-v4.sqlite3 \
  .venv/bin/alembic downgrade 20261021_0001
DATABASE_URL=sqlite:////tmp/pharmasense-phase1c-migration-v4.sqlite3 \
  .venv/bin/alembic upgrade head
```

Result: clean initialization reached `20261103_0002 (head)`; autogenerate reported no new
operations; downgrade returned to the Phase 0 baseline; re-upgrade succeeded.

```text
MYSQL_HOST=localhost MYSQL_PORT=3306 MYSQL_DATABASE=pharmasense \
MYSQL_USER=pharmasense MYSQL_PASSWORD=offline-only \
  .venv/bin/alembic upgrade head --sql > /tmp/pharmasense-phase1c-mysql.sql
```

Result: Alembic's MySQL dialect generated complete static MySQL DDL, including ASCII FDA
identifier columns, JSON columns, prefix indexes, checks, and `ON DELETE RESTRICT` constraints.
This is a compilation check, not a live MySQL execution.

```text
.venv/bin/pytest -q tests/unit/db tests/integration/test_database.py
```

Result: 6 passed, 1 skipped. The skip was the explicit live-MySQL test because
`TEST_DATABASE_URL` was not configured.

```text
PATH=.venv/bin:/Users/manaswinizagabathuni/.cache/codex-runtimes/\
codex-primary-runtime/dependencies/node/bin:$PATH make check
```

Result:

- Ruff lint: passed
- Ruff format check: 48 files formatted
- mypy strict: passed, 45 source files
- backend: 30 passed, 1 skipped in 175.98 seconds; 96.23% coverage
- Phase 1B real-archive regression: passed against all 5,912,989 scoped rows
- frontend: 5 passed; 100% statements, branches, functions, and lines

The initial plain `make check` could not find `python` because the virtual environment was not
activated. A second attempt with only the virtual environment and system paths reached frontend
lint but could not find `node`. Adding the bundled Node directory produced the successful result
above. These were host PATH limitations, not check failures.

```text
git diff --check
git ls-files .env data/raw data/processed
rg -n --hidden --glob '!*.lock' --glob '!data/**' --glob '!.git/**' \
  '(AKIA[0-9A-Z]{16}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|MYSQL_PASSWORD...)' .
docker --version
```

Result: no whitespace errors, no tracked `.env` or raw/processed FDA artifacts other than the
intended `.gitkeep` placeholders, and no matching committed secret pattern. Docker returned
`command not found`.

## Remaining verification limitation

Neither Docker nor a MySQL client/server was available, and `TEST_DATABASE_URL` was unset.
Therefore, clean initialization was executed with SQLite and MySQL DDL was compiled offline, but
the migration has not been executed against a live MySQL 8.4 instance in this environment. CI's
MySQL service and the guarded integration test are configured to verify revision
`20261103_0002` and all 13 Phase 1C tables.
