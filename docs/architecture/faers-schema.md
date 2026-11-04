# Implemented FAERS relational schema

Phase 1C implements the normalized persistence foundation in SQLAlchemy and Alembic revision
`20261103_0002`. It does not bulk-load the 2023 Q4 archive. FDA identifiers remain opaque ASCII
strings even when observed values are numeric, and partial dates remain original strings rather
than being completed or coerced.

## Source semantics reconciled with 2023 Q4

FDA's 2023 Q4 documentation defines `CASEID` as the case identifier and `PRIMARYID` as the
individual safety report version identifier. The quarterly extract contains the latest version of
each case available at extraction time; PharmaSense nevertheless models versions independently so
that versions from different quarterly snapshots can coexist without overwrite.

`DRUG_SEQ` is a relationship key within a report, not a unique DRUG-row identifier. FDA documents
that, beginning with 2021 Q4 data, one `(PRIMARYID, DRUG_SEQ)` may have multiple DRUG rows when
dose, route, or frequency details differ. Therefore, a sequence group is separate from its source
DRUG rows. THER and INDI reference that group; REAC and OUTC reference the report version.

## Provenance and control tables

| Table | Purpose and important constraints |
| --- | --- |
| `source_artifact` | One immutable archive: FDA URL, local path, year/quarter, retrieval metadata, byte size, and unique SHA-256 |
| `source_member` | One archive member: artifact FK, original path, CRC/SHA, sizes, header JSON, and observed row count; unique `(artifact_id, member_path)` |
| `ingestion_run` | Append-only attempt with parser/schema/code versions, configuration, status, counters, timestamps, and unique idempotency key |
| `ingestion_issue` | Stable issue code, severity, member/line context, safe excerpt or hash, structured details, and occurrence count |
| `rejected_record` | Quarantined source row with member/line, hash, optional local payload, and issue codes; unique per run/member/line |

Every accepted or rejected row is traceable through `source_member` to its archive and source
quarter and through `ingestion_run` to the software/configuration that processed it. Source quarter
is stored directly on report versions and drug-sequence groups for the most common filtering
paths; it is not duplicated onto every high-volume child row.

## FAERS domain tables

| Table | Grain and relationship |
| --- | --- |
| `faers_case` | One longitudinal `CASEID`; created-by-run provenance only, with no mutable “current report” pointer |
| `faers_report_version` | One immutable DEMO row keyed by `PRIMARYID`; FK to `CASEID`; unique case/version and source member/row |
| `faers_drug_sequence` | One `(PRIMARYID, DRUG_SEQ)` relationship group |
| `faers_drug` | One DRUG source row with a surrogate key and FK to its sequence group; repeated sequence rows are allowed |
| `faers_reaction` | One report-level REAC source row |
| `faers_outcome` | One report-level OUTC source row |
| `faers_therapy` | One THER source row linked to a report/drug sequence |
| `faers_indication` | One INDI source row linked to a report/drug sequence |

All verified 2023 Q4 DEMO and DRUG columns are represented. REAC, OUTC, THER, and INDI retain
their verified source columns, including their original child-row `CASEID` as `source_case_id` for
disagreement auditing. `source_extras` provides a lossless extension point for later
compatible columns but does not replace modeled fields. Original drug names, active ingredients,
role codes, reaction terms, indication terms, dose strings, and partial dates are preserved.

## Integrity and query design

- `PRIMARYID` is the report-version primary key; `(CASEID, CASEVERSION)` is also unique.
- Every source table prevents accidental replay of the same member/row.
- The unique run idempotency key prevents the same artifact/parser/schema operation from being
  promoted twice.
- Composite foreign keys require DRUG, THER, and INDI rows to reference a real drug-sequence
  group. REAC and OUTC require a real report version.
- All provenance and domain foreign keys use `ON DELETE RESTRICT`. ORM relationships use passive
  deletes; original FDA rows are not cascade-deleted.
- Indexes cover source periods, run status, case/version lookup, FDA receipt date, report/role,
  report/outcome, report/drug sequence, and original drug/reaction/indication text. MySQL text
  indexes use a 191-character prefix.
- No view joins all child collections. Each child must be aggregated at its own grain before
  combination, preventing accidental reaction × drug × outcome × therapy multiplication.

Possible duplicate submissions from different reporters are not merged. A repeated `PRIMARYID`
with conflicting content must become a high-severity ingestion conflict; it must never overwrite
stored history.

## Migration and rollback

Apply the schema with `alembic upgrade head`. Revision `20261103_0002` creates only new tables and
indexes after the Phase 0 baseline; it does not alter or delete existing application data.

The downgrade drops all Phase 1C tables in reverse foreign-key order. That is intentionally
destructive and is suitable only before data is loaded or after an independently verified backup.
Production rollback should normally deploy forward fixes instead of downgrading. MySQL DDL is not
transactional as a unit, so interrupted migrations require inspection before retry.

## Latest-version analytics

Phase 2A deliberately leaves this immutable schema unchanged. The analytics layer resolves one
latest report per case by the unique maximum numeric `CASEVERSION` and exposes invalid-only or tied
cases as explicit diagnostics. It does not maintain a mutable current-version foreign key or
delete superseded reports. See [FAERS latest-version resolution](faers-latest-version.md).

## Deferred

Parsed precision-aware date fields, product/terminology normalization, statistical signal
thresholds, uncertainty intervals, multiple-comparison controls, and historical as-of version
resolution remain outside Phase 2C.
