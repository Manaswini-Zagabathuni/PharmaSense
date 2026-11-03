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

Phase 0 provides the engineering foundation. Phase 1A adds a reviewed design and Phase 1B adds a
streaming parser and aggregate quality report for the approved FDA 2023 Q4 ASCII archive. It does
not load data into MySQL and does not calculate signals. See
[the architecture](docs/architecture/overview.md),
[FAERS ingestion design](docs/architecture/faers-ingestion.md),
[proposed schema](docs/architecture/faers-schema.md),
[official data sources](docs/data-sources/official-sources.md), and
[scientific limitations](docs/scientific-methods/faers-limitations.md).
The latest environment-specific check record is in
[Phase 0 verification](docs/phase-0-verification.md).

## Implemented services

- `mysql`: structured storage and Alembic migration target
- `api`: FastAPI liveness and database-backed readiness endpoints
- `web`: React, TypeScript, and Vite research interface shell

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
   docker compose up --build
   ```

3. Open the frontend at <http://localhost:5173>. The API is at
   <http://localhost:8000>; liveness and readiness are available at
   `/api/v1/health` and `/api/v1/ready`.

The API container applies Alembic migrations before starting. MySQL is not exposed outside the
Compose network by default.

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

## License

The source code is available under the MIT License. Source datasets retain their own terms and
must be reviewed independently before redistribution.
