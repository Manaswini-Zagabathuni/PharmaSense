# FAERS ingestion architecture

Phase 1B implements one bounded inspection command in the existing modular monolith, not a new
service. The API does not perform bulk ingestion in request handlers. Phase 1C adds the normalized
SQLAlchemy schema and migration; Phase 1D adds the restartable persistence service described below.

## Implemented flow

```text
FDA QDE index -> verified URL -> immutable raw ZIP
                                      |-> safe archive/header inspection
                                      |-> streaming table parser
                                      |-> temporary relationship-key index
                                      `-> deterministic JSON + Markdown quality reports
```

- **Acquisition:** the approved HTTPS URL was resolved from FDA's index. The archive downloaded to
  a temporary suffix, passed ZIP CRC validation, received a SHA-256, and was then promoted under
  ignored raw storage.
- **Archive validator:** rejects path traversal, encryption, duplicate normalized paths, missing
  required tables, mixed quarters, and header drift. It never extracts source rows to the working
  tree.
- **Parser:** streams unquoted, dollar-delimited ASCII directly from the ZIP; preserves source
  strings, filenames, and row numbers; and emits every line as an accepted `SourceRecord` or a
  `RejectedRecord` with a stable error code.
- **Quality analyzer:** keeps counters in memory and writes only identifiers, relationship keys,
  and hashes to temporary SQLite. Complete source records are never accumulated in memory.
- **Reporter:** atomically writes aggregate JSON and Markdown. Report identity is derived from the
  archive checksum and parser version; identical reruns do not rewrite existing reports.

Implemented modules:

```text
packages/pharmasense/ingestion/faers/
  archive.py        # safe ZIP inventory, period resolution, streaming checksum
  specification.py  # verified 2023 Q4 columns and relationships
  parser.py         # accepted/rejected streaming source events
  quality.py        # aggregate validation and temporary relationship index
  reporting.py      # deterministic machine/human reports
  cli.py            # local orchestration independent of HTTP
```

## Workflow and failure semantics

1. Require an explicit local archive path; never choose “latest” implicitly.
2. Validate ZIP paths, encryption state, table membership, year, quarter, and exact headers.
3. Scan DEMO first, followed by DRUG, REAC, OUTC, THER, and INDI.
4. Preserve values exactly; validate only structural keys, verified code/date formats, and row
   width. Unknown or malformed values receive stable issue codes rather than invented defaults.
5. Store only keys in a temporary on-disk index and check report parents, child `CASEID`, and
   THER/INDI drug-sequence relationships after streaming.
6. Require `source rows = accepted + rejected` for every table. Relationship-invalid rows are
   reported separately and never silently disappear from the parser stream.
7. Write reports atomically. If the run fails, the immutable ZIP remains and no database state is
   partially modified.

The quality report's “accepted” count means structurally parseable, not scientifically verified or
approved for later persistence. Duplicate or repeated rows remain accepted and visible. A greater
accepted-row count is not evidence of better scientific quality.

## Stable issue codes

- `HEADER_MISMATCH`
- `ROW_FIELD_COUNT_MISMATCH`
- `MISSING_REQUIRED_VALUE`
- `INVALID_IDENTIFIER`
- `INVALID_ENCODING`
- `INVALID_DATE`
- `UNKNOWN_DRUG_ROLE`
- `DUPLICATE_IDENTIFIER`
- `DUPLICATE_RECORD`
- `ORPHAN_REPORT`
- `CASEID_MISMATCH`
- `ORPHAN_DRUG_SEQUENCE`

Raw records and quarantine payloads are not logged. Reports contain aggregate counts, source
member names, sizes, headers, checksum, and parser version only.

## Verified Phase 1B behavior

The 2023 Q4 pass reconciled 5,912,989 scoped rows with zero structural rejections and zero invalid
relationships. It preserved repeated identifiers and exact duplicate rows rather than removing
them. Normal local passes completed in approximately 49-53 seconds; coverage instrumentation is
intentionally slower.

Actual inspection corrected the provisional uniqueness design: FDA permits more than one DRUG row
per `(PRIMARYID, DRUG_SEQ)` for dose, route, or frequency details. THER can likewise contain
multiple therapy intervals, and INDI can contain multiple indications. These are collection
grains, not records to deduplicate automatically.

## Phase 1C persistence boundary

Alembic revision `20261103_0002` creates immutable source provenance, report/version, drug
sequence/detail, report-child, drug-child, issue, and rejected-row tables. The design deliberately
separates the relationship group `(PRIMARYID, DRUG_SEQ)` from individual DRUG rows because the
verified source permits repeated sequence rows. All FDA rows retain member, line, and run
provenance, with source quarter normalized through the immutable archive and directly available on
report and sequence records.

Phase 1C itself wrote no parser output. Phase 1D now uses these tables directly in bounded,
checkpointed transactions and reconciles persisted records against the committed source manifest.

## Phase 1D restartable persistence

`persistence.py` implements the approved database boundary without moving work into an HTTP
handler. It validates the explicit archive and committed manifest before mutation, registers the
artifact and six archive members, and uses a deterministic key derived from archive checksum,
parser version, schema version, and source quarter.

Tables load in dependency order: DEMO, DRUG, REAC, OUTC, THER, then INDI. Every batch transaction
contains its source rows, quarantine/issues, counters, and last committed source-row checkpoint.
An interrupted transaction therefore advances neither data nor checkpoint. A resumed run streams
past committed row numbers and continues; a completed rerun returns a no-op reconciliation.

`ingestion_run.configuration` stores per-table checkpoints and counters. This avoids a new control
table while only one quarter is supported. The implementation assumes one ingestion writer per
archive; a future multi-worker loader needs database-backed work claiming rather than concurrent
mutation of the JSON checkpoint.

Structurally invalid and missing-parent rows are retained in `rejected_record` with stable issue
codes and an `ingestion_issue`. Exact duplicate child source rows remain distinct because source
member and row number—not content—define their provenance. Multiple DRUG rows continue to share a
single drug-sequence grouping.

Reconciliation records source/accepted/rejected/inserted/skipped counts, artifact-scoped and total
database counts, missing parents, integrity queries, batches, checksum, duration, and status. It
does not interpret reporting counts as incidence, prevalence, or causality.

## Deferred beyond Phase 1D

- RPSR and the deleted-case list are inventoried but not parsed.
- No parallel or multi-host ingestion coordination exists yet.
- No product or MedDRA normalization is performed.
- No statistical signal detection, ROR, PRR, AI, or retrieval work is present.
