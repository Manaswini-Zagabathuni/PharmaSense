# Phase 0 verification record

Verification performed on November 3, 2026. This record distinguishes observed results from
checks blocked by the local environment.

## Passed locally

- Python development and runtime locks installed without broken requirements.
- `pip-audit` reported no known vulnerabilities in either Python lock.
- Ruff lint and format checks passed.
- Strict mypy checking passed for 18 source files.
- Backend tests: 9 passed and 1 live-MySQL integration test skipped, with 92.91% coverage.
- Readiness now reuses one SQLAlchemy engine and connection pool; the behavior is unit tested.
- FastAPI started successfully; `/api/v1/health` returned HTTP 200.
- Without database configuration, `/api/v1/ready` returned the expected HTTP 503.
- Alembic generated valid offline MySQL upgrade SQL through revision `20261021_0001`.
- The runtime-only API dependency lock passed a clean-environment install and import check.
- `pnpm audit --audit-level=low` reported no known vulnerabilities.
- Frontend linting and TypeScript checks passed.
- Frontend tests: 5 passed with 100% measured `App.tsx` coverage.
- The Vite production build completed successfully.
- Static Compose checks confirmed exactly three services, no published MySQL port, loopback-only
  API/frontend ports, required health dependencies, and an internal backend network.
- Docker Hub returned HTTP 200 for all three pinned base-image tags.
- The environment template contains blank passwords, and Compose requires non-empty values.
- No `.env` file was present. Secret-pattern scanning found no credentials or private keys.
- CI actions are pinned to immutable commit SHAs.
- Git ignore rules cover secrets, downloaded and processed data, environments, dependencies,
  caches, coverage, and build outputs.

## Blocked locally

The `docker` executable, Docker Desktop, and alternative local container engines were not
installed. `docker compose config`, build, startup, and lifecycle commands therefore returned
`command not found`. The following checks remain unverified on this host:

- Docker Compose's own schema/interpolation validation
- API and frontend image builds
- Container image vulnerability scans
- Full MySQL/API/frontend Compose startup
- Alembic upgrade against a newly initialized live MySQL container
- HTTP 200 readiness with healthy MySQL
- HTTP 503 readiness after stopping MySQL
- Recovery to HTTP 200 after restarting MySQL

The included CI backend job starts clean MySQL 8.4, applies the migration, and executes the
integration test, but CI was not run as part of this local verification.
