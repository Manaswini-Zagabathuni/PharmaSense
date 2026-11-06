# Architecture overview

## Scope

PharmaSense begins as a modular monolith with independently runnable ingestion, normalization,
analysis, evaluation, API, and retrieval packages. Phase 0 implements only the web shell, API
system endpoints, database infrastructure, migrations, and development tooling. Phase 1A adds
reviewed ingestion contracts and design documentation. Phase 1B adds local immutable acquisition,
streaming parsing, and aggregate quality reporting for one approved quarter; it does not load
records into MySQL. Phase 1C implements the normalized relational model and migration while
leaving bulk persistence deferred. Phase 1D adds checksum-gated, restartable, batch-oriented
database ingestion and reconciliation without adding a worker service.
Phase 2A adds reusable, read-only latest-report-version resolution in the analytics layer.
Phase 2B builds source-name drug and report-level drug-reaction co-reporting summaries on that
resolved population without persisting derived data.
Phase 2C adds report-level contingency aggregation and guarded, uncorrected PRR and ROR point
estimates without introducing signal claims or clinical interpretation.
Phase 2D adds uncorrected log-ROR confidence intervals, explicit sufficiency thresholds, and a
deterministic lower-bound-first prioritization rule for research review.
Phase 3A exposes these analytics through bounded, read-only FastAPI routes backed by a separate
application service; route handlers do not contain statistical or query logic.
Phase 3B adds a responsive React dashboard that consumes those routes through a typed client and
does not reproduce analytics calculations in browser code.
Phase 4A documents and verifies the local Vite -> FastAPI -> MySQL runtime path and adds a
transactional, idempotent, explicitly synthetic demonstration seed outside production ingestion.
Phase 4B adds privacy-conscious request correlation, safe operational timing, and a minimal typed
metadata endpoint without changing analytics or persistence semantics.
Phase 4C adds fixed API response hardening, configurable trusted-host enforcement, production
configuration validation, and incremental container lifecycle restrictions.
Phase 5A adds provenance-backed source snapshot inventory and explicit completed-quarter signal
series while reusing Phase 2A version resolution and all existing statistical calculations.
Phase 5B adds a typed Historical Trends dashboard workspace over the Phase 5A API without moving
statistics, population selection, or provenance rules into the browser.
Phase 5C adds accessible, dependency-free quarter comparison for API-supplied PRR, ROR, pair
counts, and ROR intervals while preserving the detailed table and undefined-value diagnostics.

This boundary keeps scientific logic independent of transport concerns and avoids premature
distributed-system complexity.

## Target flow

```text
Official FDA/NLM sources
        │
        ▼
Ingestion ──► immutable raw artifacts and manifests
        │
        ▼
Normalization ──► versioned relational records
        │
        ▼
Signal analysis ──► dated, reproducible signal snapshots
        │
        ▼
Historical evaluation ──► time-aware FDA action comparisons
        │
        ├──► FastAPI ──► React research interface
        │
        └──► evidence retrieval ──► source-cited label answers
```

## Module boundaries

- `ingestion`: source-specific downloading and parsing; produces provenance and raw records.
- `normalization`: retains source values while generating reviewed normalized concepts.
- `analytics`: reusable relational selections that define analysis populations without mutating
  source records.
- `signals`: pure statistical calculations and versioned analytical outputs.
- `evaluation`: temporal matching between computed signals and documented actions.
- `retrieval`: label parsing, indexing, retrieval, and citation construction.
- `api`: validation and transport only; it calls application services.
- `db`: SQLAlchemy infrastructure and relational models.

The future domain modules belong under `packages/pharmasense`; scripts and route handlers must
not become alternate homes for business or statistical logic.

The FAERS-specific schema and ingestion boundaries are described in
[the implemented schema](faers-schema.md) and [ingestion architecture](faers-ingestion.md).
Latest-version selection is specified in
[the FAERS latest-version resolution design](faers-latest-version.md).
Drug and drug-reaction counting rules are specified in
[the FAERS drug-reaction analytics design](faers-drug-reaction-analytics.md).
Statistical counting, formulas, and undefined-result rules are specified in
[the FAERS signal detection design](faers-signal-detection.md).
Confidence analytics and ranking rules are specified in
[the FAERS signal prioritization design](faers-signal-prioritization.md).
The public HTTP contracts and error behavior are described in
[the read-only analytics API design](analytics-api.md).
The browser client, workspaces, configuration, and accessibility boundaries are described in
[the read-only analytics dashboard design](frontend-dashboard.md).
The Compose topology, synthetic demonstration boundary, and guarded live verification are
described in [the local full-stack runbook](local-full-stack.md).
Request IDs, JSON event fields, operation timers, metadata, and privacy exclusions are specified
in [the API observability design](observability.md).
Security boundaries, HTTP headers, trusted-host rules, and deployment limitations are described
in [the security and deployment design](security-deployment.md).
Loaded-quarter selection, reproducibility metadata, duplicate handling, and historical caveats are
described in [the historical source-quarter analytics design](historical-quarter-analytics.md).
The browser interaction, API usage, states, and provenance presentation are described in
[the Historical Trends frontend design](historical-trends-frontend.md).
The visualization scale, missing-quarter behavior, accessible representation, and intentional
non-calculation boundary are specified in
[the historical visualization design](historical-visualization.md).

## Runtime topology

Phase 0 runs three services:

- MySQL 8.4 stores structured, versioned records.
- FastAPI exposes liveness/readiness and, in later phases, research resources.
- Vite serves the React development interface.

The API can be live while not ready. `/api/v1/health` tests process liveness;
`/api/v1/ready` executes `SELECT 1` through SQLAlchemy and returns 503 on missing configuration
or failed connectivity.

MySQL is isolated on an internal Compose network and is not published to the host. Only the API
and frontend development ports bind to `127.0.0.1`.

## Configuration and provenance

Runtime configuration comes from environment variables. Secret values have no application
defaults and `.env` is ignored. Source artifacts added in Phase 1 will be immutable, checksummed,
and associated with parser and schema versions. Derived data and vector indexes must be
rebuildable from those artifacts.

## Deferred decisions

- No job queue or workflow orchestrator until measured pipeline needs justify one.
- No vector store until the label retrieval phase.
- No cloud object store until local volumes become insufficient.
- Authentication is deferred while the stack is local-only; a public deployment must add an
  external identity provider, authorization policy, request limits, and deployment threat model.
