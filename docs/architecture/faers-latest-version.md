# FAERS latest report-version resolution

Phase 2A adds a read-only analytics query for selecting the latest unambiguous report version of
each longitudinal FAERS case. It creates no table, view, migration, mutable pointer, or copied
“current” record. Every historical `faers_report_version` row remains available by `PRIMARYID`.

## Resolution rule

For each `CASEID`:

1. Treat `CASEVERSION` as valid only when the complete source string matches `[0-9]+`.
2. Convert valid values to `BIGINT` for comparison, so version `10` correctly follows version `9`
   and does not sort before it lexicographically.
3. Find the maximum numeric version within the case.
4. Return the report only when exactly one `PRIMARYID` has that maximum value.

The resolver never uses insertion order, ingestion run, source row number, creation timestamp,
FDA date, source quarter, or `PRIMARYID` as a silent tie-breaker.

Case-level diagnostics use three statuses:

- `RESOLVED`: exactly one report has the maximum valid numeric version.
- `INVALID_VERSION`: the case has no report with a numeric `CASEVERSION`.
- `VERSION_TIE`: multiple immutable reports share the maximum numeric value, including differently
  formatted strings such as `2` and `02`.

If a case contains both invalid and valid version strings, invalid rows remain stored but do not
compete with valid numeric versions. Invalid-only and tied cases are excluded from the latest-row
result rather than resolved using an unsupported fallback.

## Reusable queries

`pharmasense.analytics.faers_versions` exposes:

- `latest_report_versions_statement()`: a composable SQLAlchemy `Select` returning complete
  `FaersReportVersion` entities for resolved cases.
- `report_version_resolution_statement()`: one diagnostic row per case with status, maximum
  numeric version, and number of reports at that maximum.

Both statements execute entirely in the database using common table expressions and window
functions supported by MySQL 8.4. They are transport-independent and are not exposed through a new
HTTP endpoint in Phase 2A.

## Scientific and operational boundaries

“Latest” means the highest report version among rows currently present in the database. It does
not mean most clinically important, most recent adverse-event occurrence, or proof that a drug
caused an event. A future historical/as-of analysis must restrict the eligible source snapshot
before applying version resolution; using today's latest version would leak future follow-ups into
retrospective evaluation.

The existing `(case_id, case_version)` string index helps partition lookup, but numeric conversion
is performed at query time. Query plans must be measured after additional quarters are loaded. If
that becomes a bottleneck, a reviewed derived numeric field or materialized analytics table may be
added without changing immutable source values.
