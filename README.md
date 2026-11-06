# PharmaSense

**Research-oriented pharmacovigilance and FDA FAERS analytics**

*Detect patterns. Evaluate signals. Explore evidence.*

PharmaSense is a full-stack research platform for exploring reported drug–reaction patterns in
loaded FDA Adverse Event Reporting System (FAERS) data. It turns versioned spontaneous-report data
into bounded, inspectable analytics while preserving source provenance, historical report versions,
statistical diagnostics, and reproducible user-selected configurations.

> [!IMPORTANT]
> FAERS is a spontaneous reporting system. PharmaSense measures reporting patterns; it does not
> establish causality, incidence, clinical risk, comparative safety, or treatment recommendations.
> This project is for research and exploratory analysis, not clinical decision-making.

## Why this project exists

Large adverse-event datasets are difficult to parse, version, explore, and analyze consistently.
Naive joins can inflate counts, follow-up reports can be mistaken for independent cases, and
statistical ratios can be presented without their underlying evidence or limitations.

PharmaSense provides one traceable workflow:

| Stage | Existing behavior |
| --- | --- |
| **Discover** | Search bounded, source-derived drug and reaction terms. |
| **Explore** | Review drug summaries, reaction profiles, and observed signal detail. |
| **Analyze** | Inspect report-level contingency counts, PRR, ROR, confidence intervals, and historical quarter results. |
| **Compare** | Place two to four selected drug–reaction pairs side by side without browser-side recalculation. |
| **Reproduce** | Bookmark or copy validated analysis configurations that can be rerun against currently loaded data. |

## Implemented capabilities

- **Project Overview** — API-independent landing experience explaining the workflow and scientific
  boundary.
- **Signal Explorer and Signal Detail** — bounded signal prioritization, complete `a/b/c/d`
  contingency counts, PRR, ROR, log-ROR confidence intervals, thresholds, and explicit undefined or
  ineligible states.
- **Drug Explorer and Drug Reaction Exploration** — resolved report and case counts plus bounded
  co-reported reaction profiles.
- **Historical Trends and Historical Comparison** — per-quarter analysis over completed loaded
  source ingestions, with population exclusions and archive provenance.
- **Signal Comparison** — ordered comparison of two to four existing signal details without a
  cross-pair score or ranking.
- **Source-Term Discovery** — case-insensitive, SQL-bounded suggestions from source values; no
  automatic synonym or clinical-concept claims.
- **Reproducible Analysis Links** — validated, configuration-only URLs for Historical Trends and
  Signal Comparison. Links do not store results or freeze a dataset.
- **FAERS ingestion foundation** — immutable checksummed archives, streaming parsing, quality
  reports, normalized persistence, rejected-record tracking, and restartable idempotent batches.
- **Synthetic demo environment** — opt-in deterministic `DEMO` records for exercising the stack;
  these are not FDA data or scientific findings.
- **Operational safeguards** — request IDs, privacy-conscious structured timing, safe metadata,
  sanitized errors, trusted-host validation, security headers, and restricted development
  containers.

## Architecture

PharmaSense is a typed modular monolith. Statistical calculations and SQL population rules remain
outside HTTP route handlers and React components.

```text
React + TypeScript + Vite
          │  typed JSON over bounded read-only endpoints
          ▼
FastAPI routes, validation, security, and observability
          │
          ▼
Analytics service and reusable SQL/statistical modules
          │
          ▼
SQLAlchemy + PyMySQL
          │
          ▼
MySQL 8.4 versioned FAERS and provenance records
```

The supporting data path is:

```text
FDA quarterly ASCII archive
          │
          ▼
Streaming parser and data-quality reporting
          │
          ▼
Restartable, checksum-gated persistence
          │
          ▼
Alembic-managed normalized schema
```

Docker Compose provides the reproducible development topology. GitHub Actions validates Python and
frontend quality gates, initializes a clean MySQL database with Alembic, and runs a synthetic
frontend-to-MySQL verification job.

### Technology

| Area | Implemented technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, native browser URL/history APIs |
| API | Python 3.12, FastAPI, Pydantic settings |
| Analytics | SQLAlchemy queries and explicit Python statistical calculations |
| Storage | MySQL 8.4 with PyMySQL |
| Migrations | Alembic |
| Testing | Pytest, Vitest, Testing Library, coverage enforcement |
| Quality | Ruff, strict mypy, ESLint, TypeScript project checks |
| Runtime verification | Docker Compose and an opt-in synthetic live-stack test |
| CI | GitHub Actions with pinned action revisions and MySQL service containers |

## Quick start with Docker Compose

This is the shortest complete path. It requires Docker with Compose.

1. Create an ignored local environment file and set different, development-only values for
   `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD`:

   ```bash
   cp .env.example .env
   ```

2. Validate and start MySQL, FastAPI, and the Vite frontend:

   ```bash
   make compose-config
   docker compose up --build --detach
   docker compose ps
   ```

3. Load the explicitly synthetic demonstration population and run the live frontend-to-database
   check:

   ```bash
   make compose-seed-demo
   make verify-live
   ```

4. Open <http://127.0.0.1:5173>. The API is available at
   <http://127.0.0.1:8000>, with liveness and database-backed readiness at
   `/api/v1/health` and `/api/v1/ready`.

5. Stop the stack without deleting the database volume:

   ```bash
   make down
   ```

The API container applies `alembic upgrade head` before startup. MySQL is not published to the
host. The synthetic seed is transactional, idempotent, rejected in production mode, and contains
20 deterministic records whose displayed terms begin with `DEMO`.

See the [local full-stack runbook](docs/architecture/local-full-stack.md) for service ordering,
health checks, logs, manual verification, and safe teardown.

## Local development without Docker

The frontend overview can run without the API, but analytics require a reachable MySQL 8.4 database.
For a fully local stack, install MySQL separately and configure an ignored `.env`; when starting from
`.env.example`, change `MYSQL_HOST=mysql` to `MYSQL_HOST=127.0.0.1`.

Install the pinned dependencies:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
make install
make install-frontend
```

Apply migrations and optionally load the synthetic demo data:

```bash
make migrate
make seed-demo
```

Start the API and frontend in separate terminals with the virtual environment active:

```bash
make api
```

```bash
make web
```

The Vite development server proxies `/api` to `VITE_API_PROXY_TARGET`, which defaults to
`http://localhost:8000`. Never put secrets in `VITE_*` variables because Vite exposes them to the
browser bundle.

## Verification

The normal quality suite does not require a running database:

```bash
make check
pnpm --dir apps/web build
git diff --check
```

`make check` runs Ruff lint and formatting checks, strict mypy, backend tests with coverage, ESLint,
strict frontend type checking, and Vitest with coverage. MySQL-dependent integration tests skip
locally unless `TEST_DATABASE_URL` is configured; CI supplies a clean MySQL service and applies and
checks migrations.

With a migrated API, loaded synthetic data, and the frontend dependencies installed, run:

```bash
make verify-live
```

That opt-in test uses the real frontend client, FastAPI services, SQLAlchemy queries, and MySQL. It is
not part of the default local unit suite.

## API surface

The versioned read-only API includes:

- `GET /api/v1/health`, `/ready`, and `/info`
- `GET /api/v1/signals`
- `GET /api/v1/signals/{drug_name}/reactions/{reaction_term}`
- `GET /api/v1/drugs`
- `GET /api/v1/drugs/{drug_name}/reactions`
- `GET /api/v1/discovery/drugs` and `/discovery/reactions`
- `GET /api/v1/source-snapshots`
- `GET /api/v1/historical/signals/{drug_name}/reactions/{reaction_term}`

Interactive OpenAPI documentation is available at `/docs` while the API is running. Responses
retain request correlation and security headers. Logs exclude query strings, request bodies,
credentials, database URLs, SQL, and raw FAERS records.

## Repository map

```text
apps/web/                  React, TypeScript, Vite, and frontend tests
packages/pharmasense/      API, analytics, database, demo, telemetry, and ingestion package
migrations/                Alembic environment and versioned schema migrations
tests/                     Backend unit and optional service-backed integration tests
docs/architecture/         Design decisions, scientific query rules, and runbooks
docs/data-sources/         Official-source research and checked source manifests
docs/scientific-methods/   FAERS interpretation and scientific limitations
infra/docker/              API and frontend development Dockerfiles
data/                      Ignored local raw and processed data locations
```

## Documentation map

### Product and runtime

- [Architecture overview](docs/architecture/overview.md)
- [Project overview and demo experience](docs/architecture/project-overview.md)
- [Frontend dashboard](docs/architecture/frontend-dashboard.md)
- [Local full-stack workflow](docs/architecture/local-full-stack.md)
- [Security and deployment readiness](docs/architecture/security-deployment.md)
- [Privacy-conscious observability](docs/architecture/observability.md)

### Analytics and reproducibility

- [Read-only analytics API](docs/architecture/analytics-api.md)
- [Latest report-version resolution](docs/architecture/faers-latest-version.md)
- [Drug–reaction counting rules](docs/architecture/faers-drug-reaction-analytics.md)
- [Signal detection and PRR/ROR](docs/architecture/faers-signal-detection.md)
- [Confidence intervals and prioritization](docs/architecture/faers-signal-prioritization.md)
- [Historical source-quarter analytics](docs/architecture/historical-quarter-analytics.md)
- [Historical Trends frontend](docs/architecture/historical-trends-frontend.md)
- [Signal Comparison](docs/architecture/signal-comparison.md)
- [Source-term discovery](docs/architecture/source-term-discovery.md)
- [Reproducible analysis URLs](docs/architecture/reproducible-analysis-urls.md)

### Data engineering and scientific context

- [FAERS ingestion architecture](docs/architecture/faers-ingestion.md)
- [Normalized FAERS schema](docs/architecture/faers-schema.md)
- [Official FDA data sources](docs/data-sources/official-sources.md)
- [Quarterly extract facts and format](docs/data-sources/faers-quarterly-extracts.md)
- [FAERS scientific limitations](docs/scientific-methods/faers-limitations.md)

## Responsible use and limitations

FAERS reports are spontaneous and may be incomplete, delayed, duplicated, inaccurate, or
unverified. Public data does not provide a reliable exposure denominator, so PharmaSense cannot
calculate incidence.

PRR, ROR, confidence intervals, and prioritization describe disproportional reporting patterns.
They do not establish that a drug caused an event, quantify patient-specific or comparative risk,
or support diagnosis, prescribing, or treatment changes. Results may be affected by selective and
stimulated reporting, follow-up submissions, duplicates, underreporting, confounding by indication,
concomitant products, missing information, small counts, and terminology changes.

Historical analysis uses records currently represented by completed loaded source-quarter
ingestions. It is reproducible for that declared loaded population, but it is not necessarily a
true historical “as-of” reconstruction of everything FDA knew at that time. Reproducible URLs store
configuration rather than results; rerunning a link after data changes may produce different output.

Synthetic demonstration records are clearly labelled test fixtures. They are not FDA records,
safety findings, or clinical evidence.

## Configuration, data, and dependencies

Configuration is environment-based. `.env`, raw FDA archives, processed outputs, coverage,
dependencies, and build artifacts are ignored by Git. Secret values are never hardcoded; Compose
requires non-empty database passwords.

Only public, redistributable sources may be used. Never import restricted patient data or export
data from controlled research workspaces. Local source archives belong under ignored `data/raw` and
derived outputs under ignored `data/processed`.

Python dependencies are exactly pinned in `pyproject.toml` and resolved in `requirements.lock`; the
API image uses `requirements-runtime.lock`. Frontend dependencies are locked by
`apps/web/pnpm-lock.yaml`. Update declarations and applicable lockfiles together.

The source code is licensed under the [MIT License](LICENSE). Source datasets retain their own terms
and must be reviewed independently before redistribution.
