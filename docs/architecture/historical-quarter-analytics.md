# Historical source-quarter analytics

Phase 5A adds read-only inventory and quarter-filtered signal analysis over source records already
stored by the restartable FAERS ingestion pipeline. It does not add tables, migrations, derived
snapshots, ingestion behavior, or statistical formulas.

## Source inventory

`source_snapshot_inventory_statement()` returns one deterministically ordered row per immutable
`source_artifact`. The public inventory exposes the source quarter, archive filename and SHA-256,
source name, retrieval time, completed-run information, and report/case counts. It deliberately
does not expose storage paths, database configuration, or credentials.

The inventory distinguishes three states:

- `known_in_provenance` means an immutable `source_artifact` row exists;
- `persisted_report_count` includes report versions attached to any ingestion run, including a
  paused or failed attempt whose committed checkpoints remain restartable; and
- `successfully_loaded_report_count` and `successfully_loaded_case_count` count only report rows
  attached to an ingestion run whose status is `COMPLETED`.

An archive can therefore be known, and can even have checkpointed report rows, without being an
eligible completed source quarter for historical analytics.

## Population selection

The Phase 5A rule is identified as
`COMPLETED_INGESTIONS_IN_INCLUSIVE_QUARTER_RANGE`:

1. validate a caller-supplied inclusive `YYYYQn` range;
2. find source quarters in that range with at least one report from a completed ingestion run;
3. restrict eligible report versions to those completed runs and selected source quarters; and
4. apply the existing Phase 2A resolution rule inside that restricted population.

The maximum numeric `CASEVERSION` is selected per `CASEID`. Invalid-only cases and ambiguous
numeric maximum ties remain excluded. No ingestion timestamps, source row order, FDA dates, or
identifiers are used as tie-breakers. With no population filter, all existing Phase 2A–2D query
builders retain their previous behavior.

Range-level metadata resolves each longitudinal case once across the complete selected range. A
case represented in several selected source quarters therefore contributes at most one resolved
report to that range population. The metadata records the requested range, actual completed and
loaded quarters selected, resolved report/case counts, and invalid-version and version-tie
exclusions.

## Quarter signal series

Each returned quarter is analyzed independently. The shared Phase 2A resolver is restricted to
that single quarter, then the existing report-presence CTEs create one row per report/drug name
and report/reaction term. Duplicate source drug or reaction rows cannot multiply contingency
cells. The existing Phase 2C contingency builder and Phase 2D PRR, ROR, uncorrected log-ROR
confidence interval, eligibility, and prioritization functions are reused unchanged.

A longitudinal case can appear once in more than one per-quarter measurement when distinct report
versions occur in different source quarters. Those values describe separate source-quarter
populations and must not be summed to obtain a unique multi-quarter case count. Range metadata
provides the separately resolved union population.

The database schema stores one immutable `PRIMARYID` report version, so an identical `PRIMARYID`
cannot be duplicated as separate report rows across archives. Report versions are associated with
the ingestion run that persisted them. Phase 5A does not infer repeated archive membership that
is not represented by the current provenance model.

## Loaded-source filtering is not historical as-of reconstruction

The result answers: “what is the reporting measurement after filtering the report rows currently
loaded from these completed source quarters?” It does not reconstruct exactly what FDA, a user, or
the database knew on an historical date. In particular, the current schema does not preserve a
many-to-many membership history for the same `PRIMARYID` repeated in several quarterly archives.
No publication cutoff or retrospective knowledge boundary is inferred. A true as-of analysis
would require an explicitly modeled snapshot-membership and availability-time contract.

## API

- `GET /api/v1/source-snapshots?limit=100` returns a bounded archive inventory (maximum 200).
- `GET /api/v1/historical/signals/{drug}/reactions/{reaction}` requires `start_quarter` and
  `end_quarter`, accepts at most 80 inclusive quarters, and returns deterministic selected-quarter
  metadata plus one result per successfully loaded quarter.

An empty selected range is HTTP 200 with no items and zero metadata counts. Historical operations
use the existing sanitized database errors, request IDs, security headers, and privacy-conscious
stable operation timing. Drug and reaction values are not included in operation logs.

## Scientific limitations

Quarter comparisons are descriptive reporting measurements, not incidence estimates, causal
effects, clinical risks, or safety recommendations. Changing report volume, stimulated reporting,
underreporting, follow-up behavior, duplicate submissions, missing data, concomitant drugs,
confounding, terminology changes, and source processing can change measurements across quarters.
Small or zero contingency cells can make PRR, ROR, or confidence intervals undefined. The API
preserves those explicit diagnostics and applies no hidden continuity correction.

Frontend work is intentionally deferred in Phase 5A. The reusable query, service, typed API, and
scientific contract are established first; the existing dashboard remains unchanged.
