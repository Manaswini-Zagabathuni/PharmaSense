# Proposed FAERS relational schema

This is a Phase 1A design, not an applied migration. Phase 1B must implement it in a new Alembic
revision after verifying the selected archive's README. Identifiers from FDA are stored as opaque
strings even when they currently contain digits, preventing loss of leading zeros or future
format assumptions. All timestamps are UTC.

## Provenance and control tables

| Table | Purpose and important constraints |
| --- | --- |
| `source_artifact` | One immutable ZIP: source system/era, quarter, format, FDA URL, posted date, retrieval time, byte size, SHA-256, local object key; unique SHA-256 and unique `(source, quarter, format, sha256)` |
| `source_member` | One accepted ZIP member: artifact FK, logical table, original member path, member SHA-256, byte size, observed header JSON; unique `(artifact_id, member_path)` |
| `ingestion_run` | Attempt identity, artifact FK, parser/schema versions, configuration JSON, status, start/end timestamps, code revision, counters; unique idempotency key derived from artifact hash plus parser/schema versions |
| `ingestion_issue` | Run/member/line, severity, stable reason code, field name, safe value excerpt or hash, details JSON, occurrence count |
| `rejected_record` | Quarantined row reference with member and line, raw-row hash, bounded encrypted-or-local-only payload, and rejection reasons; never written to application logs |

Runs are append-only audit events. A failed run can be retried; promotion into canonical tables is
transactional by member/batch, and a completed idempotency key is a no-op with a reported status.

## Domain tables

| Table | Key and selected columns |
| --- | --- |
| `faers_case` | PK `case_id`; first/last observed quarter and timestamps only—no destructive “current report” copy |
| `faers_report_version` | PK `primary_id`; FK `case_id`; nullable parsed `case_version`; quarter/artifact/member/run FKs; source row number; FDA dates in raw text plus nullable parsed values; all other DEMO source fields; unique `(case_id, case_version)` only when version is present and verified unique |
| `faers_drug` | Surrogate PK; FK `primary_id`; `drug_seq`; original `role_code`, `drug_name`, active ingredient, route, dose, and other DRUG values; source row number; unique `(primary_id, drug_seq)` after verification |
| `faers_reaction` | Surrogate PK; FK `primary_id`; original `preferred_term`; optional source fields; source row number; unique `(source_member_id, source_row_number)` |
| `faers_outcome` | Surrogate PK; FK `primary_id`; original outcome code; source row number; unique `(source_member_id, source_row_number)` |
| `faers_therapy` | Surrogate PK; FK (`primary_id`, `drug_seq`) to DRUG; original start/end/duration text plus nullable parsed values; source row number |
| `faers_indication` | Surrogate PK; FK (`primary_id`, `drug_seq`) to DRUG; original indication term; source row number |

Every domain row retains `source_member_id`, `source_row_number`, `ingested_at`, and the run that
created it. A compact JSON `source_extras` column may preserve unmodeled columns, but it is not a
substitute for typed fields used in filtering or integrity checks. Raw source files remain the
immutable system of record.

Foreign keys use `RESTRICT` for source provenance and report parents. Canonical source rows are
not cascade-deleted. Indexes cover `case_id`, `(case_id, case_version)`, report foreign keys,
`(primary_id, role_code)`, and exact original drug/reaction text where MySQL index length permits.

## Version and duplicate policy

`CASEID` identifies the longitudinal case and `PRIMARYID` identifies one submitted report version.
All versions are retained. A `latest_report_version` database view (or equivalent query) ranks
verified versions within each case by case version, FDA receipt date, and deterministic ID
tie-breaker. It is explicitly a convenience view; historical analyses must apply their own
as-of cutoff and never use a future follow-up.

Three different situations are not conflated:

1. **Exact file/run replay:** prevented by artifact hash and run idempotency key.
2. **The same FDA report version:** prevented by `primary_id` and validated for content conflicts.
3. **Possible duplicate submissions from different reporters:** not automatically merged. FDA
   acknowledges these exist, but similarity-based linkage can create false matches. A later,
   separately versioned candidate-link table may support review without changing source rows.

If a repeated `primary_id` differs in content, ingestion fails promotion and records a
high-severity provenance conflict rather than overwriting either value.

## Preventing join multiplication

REAC and OUTC are report-level collections; THER and INDI are drug-level collections. Queries must
aggregate each collection at its own grain before combining them. No convenience view joins all
children into one flat rowset. A future drug–reaction analysis table will deliberately form one
pair per eligible `(primary_id, drug_id, reaction_id)` under a documented role/version policy and
will not join outcomes, therapies, or indications into that pairing operation.

## Missing, malformed, and unknown values

- Preserve the decoded source token and distinguish empty, absent column, invalid, and parsed
  values. Never turn an invalid value into zero or an invented date.
- Parse partial FDA dates into a precision-aware representation (`year`, optional month/day,
  precision code) rather than filling missing components.
- Unknown role/outcome/unit codes remain in the row and generate a warning; structural key errors,
  malformed row width, orphan parent IDs, or unsafe archive paths reject the row or artifact.
- Child `CASEID` disagreement, duplicate sequence keys, decode replacement characters, and
  unexpected headers are measured and surfaced. Required-header drift blocks ingestion.
- Quality thresholds are configuration recorded on the run. Reports include totals, accepted,
  rejected, warned, orphaned, and reason-code counts per member; no silent drops are allowed.
