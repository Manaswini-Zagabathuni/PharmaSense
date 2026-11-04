# Local full-stack environment

## Purpose and boundary

Phase 4A provides a reproducible local path through the React dashboard, FastAPI analytics API,
and MySQL 8.4. It does not change the API contract, the resolved-report population, statistical
calculations, or production FAERS ingestion.

The Compose topology is:

```text
browser -> 127.0.0.1:5173 (Vite)
                    |
                    | /api proxy on the frontend network
                    v
             api:8000 (FastAPI)
                    |
                    | SQLAlchemy/PyMySQL on the internal backend network
                    v
              mysql:3306 (MySQL 8.4)
```

MySQL has no host-published port. The API and Vite ports bind only to `127.0.0.1`. Inside
Compose, services use the `api` and `mysql` DNS names rather than `localhost`.

## Startup and readiness

Copy `.env.example` to the ignored `.env` file and replace both blank password values with
different development-only secrets. Compose rejects blank values. Then run:

```bash
docker compose config
docker compose up --build --detach
docker compose ps
curl --fail http://127.0.0.1:8000/api/v1/health
curl --fail http://127.0.0.1:8000/api/v1/ready
```

MySQL first passes its container health check. The API container then applies `alembic upgrade
head` before starting Uvicorn. `/health` reports process liveness; `/ready` executes `SELECT 1`
with the configured application account and returns 503 when MySQL is unavailable. The web
container waits for API readiness.

`docker compose logs api mysql web` provides sanitized service output. Application code does not
log database URLs or passwords.

## Synthetic demonstration population

The opt-in demonstration seed is separate from FDA ingestion:

```bash
make compose-seed-demo
```

The command requires the explicit `--confirm-synthetic` flag internally, refuses to run when
`APP_ENVIRONMENT=production`, and is idempotent. It inserts 20 deterministic records under the
`PHARMASENSE_DEMO` source system. Every displayed name starts with `DEMO`; provenance metadata
marks `fda_data` as false. The population supplies non-zero contingency cells and a prioritized
example so all four dashboard flows can be exercised. It is not an FDA extract, safety finding,
or scientific result.

For a locally installed API connected to a standalone MySQL database, apply migrations and run:

```bash
alembic upgrade head
make seed-demo
```

The seed never alters production analytics logic. It uses the same normalized tables and queries
as ordinary ingested data. The seed is transactional: a failed first run is rolled back, while a
completed rerun is a no-op keyed by a stable artifact checksum.

## Live verification

With the stack running and demo data loaded:

```bash
make verify-live
```

This guarded Vitest/JSDOM check uses the real typed frontend client. It checks API liveness and
readiness, renders prioritized signals, opens signal detail, switches to the drug list, and opens
co-reported reactions. Because those requests traverse FastAPI services and SQLAlchemy queries,
the command verifies the frontend-client -> API -> analytics-service -> MySQL path. The normal
unit suite leaves this test skipped so it never silently depends on a local service.

Manual browser verification remains useful for layout and proxy behavior: open
<http://127.0.0.1:5173>, inspect `DEMO DRUG ALPHA / DEMO REACTION ALPHA`, then open its reaction
profile in Drug Explorer.

Stop containers without deleting the database volume:

```bash
docker compose down
```

`docker compose down --volumes` deletes the entire local MySQL volume, including any non-demo
data, and is therefore not part of the normal workflow.

## Configuration

- `MYSQL_*` variables configure both MySQL and the API; no password has a default.
- `VITE_API_BASE_URL` defaults to `/api/v1`, keeping browser requests same-origin.
- `VITE_API_PROXY_TARGET` defaults to `http://localhost:8000` outside Compose and is overridden
  to `http://api:8000` in the web container.
- `LIVE_API_BASE_URL` can override the default live-test URL
  `http://127.0.0.1:8000/api/v1`.

Never place secrets in `VITE_*` variables: Vite exposes them to browser code. `.env`, raw FDA
archives, processed data, coverage, dependencies, and build output remain ignored by Git.

## Scientific limitations

FAERS reports are spontaneous reports subject to underreporting, reporting bias, duplicate
submissions, confounding, and incomplete information. Reporting patterns do not establish
causality or incidence. Synthetic demo data is not FDA evidence. PharmaSense is research software,
not a clinical decision system.
