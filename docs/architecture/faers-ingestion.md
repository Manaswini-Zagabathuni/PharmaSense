# FAERS ingestion architecture

Phase 1B should implement one bounded command in the existing modular monolith, not a new service.
The API will not perform bulk ingestion in request handlers.

## Components

```text
FDA QDE index -> catalog resolver -> downloader -> immutable raw artifact
                                           |-> archive/header validator
                                           |-> streaming table parser
                                           |-> row validator/transformer
                                           |-> staged persistence -> canonical promotion
                                           `-> reconciliation + quality report
```

- **Catalog resolver:** accepts an allowlisted FDA URL and explicit year/quarter/format; captures
  the landing-page and resolved archive URLs. It never chooses “latest” implicitly.
- **Downloader:** HTTPS only, bounded redirects/size/timeouts, streamed SHA-256, temporary file,
  ZIP validation, and atomic promotion. No extraction paths are trusted.
- **Archive validator:** rejects encryption, path traversal, links, duplicate normalized names,
  decompression-ratio/size limit violations, missing required members, and header drift.
- **Parser:** streams the dollar-delimited ASCII members, retains line numbers and source tokens,
  validates row width, and does not normalize drug or reaction text.
- **Validator/transformer:** enforces structural keys and relationships, performs explicit
  precision-aware date parsing, and emits accepted rows or typed issues/rejections.
- **Persistence:** writes bounded batches to run-scoped staging tables with SQLAlchemy Core
  parameter binding, reconciles counts/keys, then promotes transactionally to canonical tables.
- **Reporter:** writes a machine-readable manifest plus a human-readable summary of checksums,
  versions, counts, timings, issues, and final status. It never claims scientific validation.

Module target:

```text
packages/pharmasense/ingestion/faers/
  catalog.py       # explicit source metadata
  download.py      # safe immutable acquisition
  archive.py       # ZIP and member validation
  parser.py        # streaming source records
  validation.py    # structural and field-level decisions
  transform.py     # typed, lossless transformations
  persistence.py   # staging, reconciliation, promotion
  reporting.py     # manifests and quality summaries
  service.py       # orchestration independent of CLI/HTTP
```

## Workflow and failure semantics

1. Resolve an explicit catalog entry; create a pending run.
2. Download once to temporary storage, hash while streaming, validate, then make immutable.
3. Read the included README and validate expected members/headers before row persistence.
4. Load DEMO first, then DRUG/REAC/OUTC, then THER/INDI so parent integrity can be checked.
5. Parse and persist in bounded batches to run staging; record every rejected line and issue.
6. Reconcile source rows against accepted plus rejected rows and validate FK/key counts.
7. Promote in a transaction; mark complete only after reconciliation and report creation.
8. On failure, retain the artifact, run metadata, and diagnostic counts; canonical tables remain
   unchanged. Retry uses the same artifact hash and a new attempt linked to the idempotency key.

Database credentials come only from existing environment configuration. Logs contain run IDs,
hash prefixes, and aggregate counts—not raw records, credentials, URLs with secrets, or full
quarantine payloads.

## Phase 1B implementation plan and acceptance criteria

### 1. Schema and migration

Implement reviewed SQLAlchemy models, staging/control/domain tables, constraints, indexes, and a
new Alembic migration. A clean MySQL database upgrades and downgrades; relationship and uniqueness
tests run against MySQL.

### 2. Safe acquisition and manifest

Implement the explicit 2023 Q4 catalog entry and downloader. Unit tests use local byte streams and
temporary ZIPs; an opt-in integration test may fetch only the approved FDA archive. The manifest
contains URLs, posted/retrieval time, byte size, SHA-256, format, quarter, code/parser/schema
versions, and immutable path. Re-running acquisition does not duplicate the artifact.

### 3. Streaming parser and validation

Implement archive/header protections, stream each required table, preserve source text/ordinal,
and emit typed issues. Tests use minimal clearly synthetic fixtures and malformed structural
cases, not invented scientific observations. Unknown optional columns are preserved and reported;
missing required columns fail before load.

### 4. Staging, reconciliation, and promotion

Load in bounded batches, enforce parent and drug-sequence relationships, reconcile every source
row, and promote atomically. Re-running the same artifact/parser/schema combination is a no-op;
conflicting `PRIMARYID` content fails safely. A failed run cannot partially alter canonical data.

### 5. Pilot execution and report

Only after explicit approval, download and ingest 2023 Q4 ASCII. Publish actual file hashes, row
counts, reject/warning counts, elapsed time, and environment in an ignored local run report (or a
small non-data manifest if approved for Git). Do not infer signals or make causal/incidence claims.
All Phase 0 and new checks must pass.
