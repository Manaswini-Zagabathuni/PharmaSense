# Historical Trends frontend

Phase 5B adds a third dashboard workspace for inspecting API-calculated reporting measurements
across successfully loaded FAERS source quarters. It is a typed, read-only presentation layer and
does not implement statistical formulas, population resolution, or source selection rules.

## Data flow

The workspace uses the centralized browser API client and consumes two Phase 5A endpoints:

- `GET /api/v1/source-snapshots?limit=200` supplies archive provenance and determines which
  quarters contain reports from completed ingestion runs. Those quarters populate the inclusive
  start and end selectors. Provenance-known but incomplete quarters remain visible in the
  reproducibility panel but are not offered as analysis boundaries.
- `GET /api/v1/historical/signals/{drug}/reactions/{reaction}` supplies the selected population
  metadata and each quarter's contingency counts, PRR, ROR, ROR confidence interval, eligibility,
  prioritization status, and diagnostic reasons. Drug and reaction path components are URL-encoded;
  start and end quarters are encoded query parameters.

React performs no PRR, ROR, confidence interval, contingency, trend, eligibility, or prioritization
calculation. It only formats values and diagnostic codes returned by FastAPI. An absent estimate is
rendered as `Not defined` with the API-provided reason.

## Interaction and states

The existing workspace navigation exposes `Historical Trends`. The form requires a source drug
name, reaction term, and inclusive loaded-quarter range. It provides explicit initial, validation,
loading, empty, error, and retry states. API failures never produce placeholder or fabricated
analytics.

The results table is horizontally scrollable at narrow widths and uses semantic table headers.
Native labeled inputs, selects, buttons, status regions, alerts, and an accessible `details`
element support keyboard and assistive-technology use. Existing responsive breakpoints and visible
focus behavior are preserved.

## Provenance and reproducibility

An expandable secondary panel shows:

- requested and actually selected quarters;
- range-level resolved report and case counts;
- invalid-version and version-tie exclusions;
- archive filename and SHA-256 identity;
- completed report and case counts; and
- the server-provided historical-method notice.

The main table shows per-quarter populations. These are separate resolved source-quarter
populations and must not be summed as unique multi-quarter case counts. Range-level counts come
directly from Phase 5A metadata.

## Scientific boundary

The workspace states that FAERS measurements describe reported associations, not causality,
incidence, clinical risk, comparative safety, or treatment recommendations. Quarter comparisons
can be affected by reporting behavior, follow-ups, duplicates, underreporting, confounding, and
terminology changes. Filtering records currently loaded from selected source quarters is not a
true historical as-of reconstruction.

Phase 5C adds a dependency-free, accessible metric comparison above the detailed table. Its
presentation-only coordinate scaling, missing-value rules, and non-calculation boundary are
documented in [historical visualization and comparison](historical-visualization.md).
