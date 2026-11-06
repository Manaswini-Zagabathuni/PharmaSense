# PharmaSense

**AI-Powered Drug Safety Intelligence Platform**

*Detect patterns. Evaluate signals. Explore evidence.*

PharmaSense is a research-oriented platform for exploring potential drug–adverse-event
reporting signals in public FDA adverse-event data and connecting those signals to official
safety actions and labeling evidence.

> [!IMPORTANT]
> PharmaSense is research software, not a medical device or clinical decision-support system.
> A reporting association is not proof of causation, incidence, or comparative safety. Do not
> use this project to diagnose, treat, prescribe, or change medication.

Phase 0 provides the engineering foundation. Phase 1A adds a reviewed design, Phase 1B adds a
streaming parser and aggregate quality report for the approved FDA 2023 Q4 ASCII archive, and
Phase 1C adds the normalized SQLAlchemy schema and Alembic migration. Phase 1D adds restartable,
checksum-gated database ingestion and reconciliation. Phase 2 adds read-only latest-version,
drug-reaction, disproportionality, confidence, and prioritization analytics. Phase 3A exposes
those analytics through a bounded, read-only API, and Phase 3B provides a responsive React
research dashboard over that API. Phase 4A adds an opt-in synthetic demonstration population and
a guarded live frontend-to-MySQL verification workflow. Phase 4B adds request correlation,
privacy-conscious operation timing, and safe application metadata. See
[the architecture](docs/architecture/overview.md),
[the local full-stack runbook](docs/architecture/local-full-stack.md),
[the observability design](docs/architecture/observability.md),
[analytics API](docs/architecture/analytics-api.md),
[frontend dashboard](docs/architecture/frontend-dashboard.md),
[FAERS ingestion design](docs/architecture/faers-ingestion.md),
[implemented schema](docs/architecture/faers-schema.md),
[official data sources](docs/data-sources/official-sources.md), and
[scientific limitations](docs/scientific-methods/faers-limitations.md).
The latest environment-specific check record is in
[Phase 1D verification](docs/phase-1d-verification.md).

## Implemented services

- `mysql`: structured storage and Alembic migration target
- `api`: FastAPI system endpoints and versioned read-only FAERS analytics
- `web`: React, TypeScript, and Vite read-only analytics dashboard

There is intentionally no Redis, Kafka, workflow orchestrator, retrieval service, or worker yet.

## Prerequisites

- Python 3.12
- Node.js 22 and pnpm 11.25.0
- MySQL 8.4, or Docker with Docker Compose

## Docker setup

1. Copy the environment template, then set both blank password values to different, strong
   development-only secrets. Compose rejects missing or empty passwords:

   ```bash
   cp .env.example .env
   ```

2. Start the stack:

   ```bash
   docker compose config
   docker compose up --build --detach
   docker compose ps
   ```

3. Open the frontend at <http://localhost:5173>. The API is at
   <http://localhost:8000>; liveness and readiness are available at
   `/api/v1/health` and `/api/v1/ready`.

The API container applies Alembic migrations before starting. MySQL is not exposed outside the
Compose network by default.

4. Load the explicitly synthetic, idempotent demonstration population and verify the complete
   frontend-client -> API -> analytics-service -> MySQL path:

   ```bash
   make compose-seed-demo
   make verify-live
   ```

   The seed contains 20 deterministic `DEMO`-named reports and is not FDA data or evidence. See
   the [local full-stack runbook](docs/architecture/local-full-stack.md) for its provenance,
   safety boundary, live-test behavior, and manual dashboard checks.

5. Stop the services while preserving the database volume:

   ```bash
   docker compose down
   ```

## Local development

Create and activate a virtual environment, then install the pinned project dependencies:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
pnpm --dir apps/web install --frozen-lockfile
```

Set database variables in your shell or an ignored `.env`. Then run:

```bash
alembic upgrade head
uvicorn pharmasense.api.main:app --reload
pnpm --dir apps/web dev
```

The liveness endpoint confirms the process can serve requests. The readiness endpoint performs
`SELECT 1` against MySQL and returns HTTP 503 if configuration or connectivity is unavailable.
Interactive development documentation at `/docs` includes the Phase 3A endpoints:

- `GET /api/v1/info`
- `GET /api/v1/signals`
- `GET /api/v1/signals/{drug_name}/reactions/{reaction_term}`
- `GET /api/v1/drugs`
- `GET /api/v1/drugs/{drug_name}/reactions`

API responses include `X-Request-ID`. Request and analytics completion events are emitted as
privacy-conscious JSON logs containing stable operation fields and durations, never request
bodies, query strings, credentials, database URLs, or raw FAERS records.

All analytics are research-only reporting patterns. They do not establish causality or incidence
and must not be used for clinical decision-making.

The dashboard opens on Signal Explorer and provides a Drug Explorer workspace. Vite uses
`VITE_API_BASE_URL=/api/v1` by default and proxies `/api` requests to
`VITE_API_PROXY_TARGET=http://localhost:8000` during local development. Do not place secrets in
`VITE_*` variables because Vite bundles them into browser code.

For a standalone local MySQL installation, apply migrations, seed the optional demonstration
population, and start both processes:

```bash
alembic upgrade head
make seed-demo
uvicorn pharmasense.api.main:app --reload
pnpm --dir apps/web dev
```

Then `make verify-live` exercises the real API. The normal `make check` suite does not require a
running database or backend; the guarded live dashboard test runs only through `verify-live`.

The API container runs `alembic upgrade head` before startup. For local MySQL, apply the same
migration explicitly and inspect the active revision:

```bash
alembic upgrade head
alembic current
```

Revision `20261103_0002` creates the Phase 1C FAERS persistence tables. Its downgrade removes those
tables and is destructive once data exists; use a verified backup and prefer a forward migration.

## Quality checks

```bash
make check
```

This runs Ruff lint/format checks, mypy, pytest with coverage, ESLint, TypeScript, and Vitest.
GitHub Actions runs the same checks and verifies the migration against a clean MySQL service.

## Dependency locking

Runtime and development dependencies are exactly pinned in `pyproject.toml`; their resolved
Python 3.12 development environment is captured in `requirements.lock`. The API image installs
the smaller runtime-only `requirements-runtime.lock`. Frontend transitive dependencies are locked
in `apps/web/pnpm-lock.yaml`. When dependencies change, update both applicable Python locks or the
frontend declaration and lock together, then verify installation in a clean environment.

## Data policy

Only public, redistributable sources may be used. Never import restricted patient data or export
data from controlled research environments. Downloaded archives and derived datasets belong in
the ignored `data/raw` and `data/processed` directories.

## FAERS 2023 Q4 local inspection

The raw archive is intentionally not distributed with the repository. After independently
downloading the approved file from FDA, verify its SHA-256 is
`7e6b72848ed670900eaf78d24983c845f077091f71ffa7b9c310d590faebac62` and place it at
`data/raw/faers/2023Q4/faers_ascii_2023Q4.zip`. Then run:

```bash
python -m pharmasense.ingestion.faers.cli \
  data/raw/faers/2023Q4/faers_ascii_2023Q4.zip \
  --json-report data/processed/faers/2023Q4/quality-report.json \
  --markdown-report data/processed/faers/2023Q4/quality-report.md
```

Both outputs are aggregate local artifacts and remain ignored. Identical reruns leave existing
report files unchanged. See [Phase 1B verification](docs/phase-1b-verification.md) for observed
archive facts and limitations.

## FAERS 2023 Q4 database ingestion

Apply migrations and validate the archive before loading:

```bash
alembic upgrade head
python -m pharmasense.ingestion.faers.ingest_cli \
  data/raw/faers/2023Q4/faers_ascii_2023Q4.zip \
  --manifest docs/data-sources/manifests/faers-2023q4-ascii.json \
  --year 2023 --quarter 4 \
  --json-report data/processed/faers/2023Q4/validation.json \
  --markdown-report data/processed/faers/2023Q4/validation.md \
  --validate-only
```

Run or resume the database load with:

```bash
make ingest-faers
# Optional smaller transactions:
make ingest-faers FAERS_BATCH_SIZE=1000
```

The equivalent `pharmasense-faers-ingest` command accepts `--batch-size`. `--max-batches N`
intentionally pauses after `N` committed batches for operationally bounded runs; invoking the same
command again resumes from the last committed source row. A completed rerun is a reported no-op.
Reconciliation is written under ignored `data/processed` storage as JSON and Markdown.

Ingestion requires a database at Alembic revision `20261103_0002`. It validates the committed
manifest checksum before database mutation and never chooses a “latest” quarter implicitly.

## License

The source code is available under the MIT License. Source datasets retain their own terms and
must be reviewed independently before redistribution.
