# Historical visualization and comparison

Phase 5C adds an accessible visual comparison to the Phase 5B Historical Trends workspace. It is
a dependency-free React/CSS presentation of the existing Phase 5A response and does not change
the API, historical population, ingestion, or statistical calculations.

## API-supplied values

The comparison receives the same typed `HistoricalSignalResponse` as the detailed table. It can
display, one metric at a time:

- PRR point estimates;
- ROR point estimates;
- drug–reaction pair-report cell `a`;
- ROR confidence interval endpoints and the ROR point estimate; and
- API-provided evaluability and prioritization status.

Every visible number is formatted directly from those response fields. The browser does not
calculate PRR, ROR, confidence intervals, significance, a composite score, smoothing,
interpolation, prediction, or causal interpretation.

## Display coordinates

For a selected metric, CSS bar or interval coordinates are normalized to the largest finite API
value currently displayed. This is presentation-only pixel scaling; the normalized coordinate is
not shown as data, persisted, ranked, or used to label direction or importance. Numeric API values
remain visible beside every mark and in the unchanged detailed table.

Requested quarters are enumerated chronologically from the response metadata. A requested quarter
without an API result is rendered as `No loaded result`. It is not interpolated. A `null` metric or
interval endpoint is rendered as `Not defined` with its API diagnostic reason. A server-supplied
numeric zero remains visibly `0`; undefined and missing values are never converted to zero.

## Accessibility

The comparison uses a labeled region, native radio controls, and a semantic ordered list. Each row
contains its quarter, formatted numeric value or explicit unavailable state, and text status.
Visual bars and interval marks are decorative and hidden from assistive technology. A text legend
supplements pattern and color, and status is never communicated by color alone. The existing
semantic results table remains the complete accessible data representation.

On narrow screens, controls wrap and each comparison row stacks without removing values or
diagnostics. Reduced-motion behavior remains unchanged because the comparison adds no animation.

## Interpretation boundary

Visual proximity or differences between quarters do not establish a trend, causality, incidence,
clinical risk, comparative safety, or a treatment recommendation. Changes can reflect reporting
behavior, follow-ups, duplicates, underreporting, confounding, terminology, or loaded-population
changes. The comparison represents loaded-source filtering, not necessarily a historical as-of
reconstruction.
