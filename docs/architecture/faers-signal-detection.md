# FAERS statistical signal detection foundation

Phase 2C adds read-only report-level contingency queries and uncorrected proportional reporting
ratio (PRR) and reporting odds ratio (ROR) calculations. These values are disproportionality
measurements for signal exploration. They do not establish causality, measure incidence, compare
absolute risks, or support clinical recommendations.

## Analysis population

The population is exactly the Phase 2A result from `latest_report_versions_statement()`: one
unambiguously resolved highest numeric `CASEVERSION` for each longitudinal `CASEID`. Cases with
invalid-only versions or a tied numeric maximum are excluded. Historical versions remain stored
but do not enter Phase 2C calculations.

Phase 2C consumes the public Phase 2B presence CTEs. Drug and reaction presence are each reduced
to one row per resolved report and source-value group before they are joined or counted. Database
collation defines source-value equality, consistent with Phase 2B.
Drug presence currently includes every preserved FDA role code; primary suspect, secondary
suspect, concomitant, and interacting roles are not filtered or combined into a causal category.

## Report-level contingency table

For a selected drug and reaction, every resolved report is classified exactly once:

| | Reaction present | Reaction absent |
| --- | ---: | ---: |
| Drug present | `a` | `b` |
| Drug absent | `c` | `d` |

- `a`: reports containing both the selected drug and reaction;
- `b`: reports containing the drug but not the reaction;
- `c`: reports containing the reaction but not the drug; and
- `d`: reports containing neither.

The invariant is `N = a + b + c + d`, where `N` is the complete resolved latest-report
population, including reports with no stored drug or reaction rows. Duplicate source rows and
multiple sequences containing the same drug name do not increase a cell. A report containing
multiple distinct drugs and reactions can contribute to multiple different pair tables, but only
once to any one pair table.

`drug_reaction_contingency_statement(drug_name, reaction_term)` returns one table even when the
population or selected pair is empty. `observed_drug_reaction_contingencies_statement()` returns
database-aggregated tables for pairs observed at least once (`a > 0`), providing a composable basis
for future ranking and filtering without loading source rows into application memory.

## Point-estimate formulas

For a validated table, Phase 2C calculates:

```text
PRR = [a / (a + b)] / [c / (c + d)]
ROR = (a × d) / (b × c)
```

`calculate_disproportionality()` returns typed PRR and ROR estimates together with the underlying
table. No Haldane–Anscombe or other continuity correction is applied. Consequently, these are
raw point estimates and must not be interpreted as adjusted or stabilized estimates.

## Undefined and invalid results

An undefined metric is returned as `value=None` with a stable `UndefinedMetricReason`; infinity is
never returned as a signal value.

- An empty population makes both metrics undefined.
- PRR is undefined when there are no drug reports, no non-drug comparator reports, or zero
  reaction reports in the non-drug comparator group.
- ROR is undefined when `b` or `c` is zero.
- A finite zero is retained when the numerator is zero and the relevant denominators are nonzero.
- A non-finite floating-point result is rejected explicitly.
- Negative, non-integer, or internally impossible marginal counts raise `ValueError` rather than
  producing a metric.

Small counts can yield unstable finite estimates. Phase 2C deliberately adds no minimum-count
threshold, confidence interval, significance test, multiple-comparison adjustment, or signal
classification rule. Those require a separately reviewed statistical phase.

## Interfaces and boundaries

`pharmasense.analytics.signals` exposes:

- `drug_reaction_contingency_statement(drug_name, reaction_term)`;
- `observed_drug_reaction_contingencies_statement()`;
- `ContingencyTable` and its validated `from_margins()` constructor; and
- `calculate_disproportionality(table)` returning typed PRR/ROR results.

SQL performs population selection, presence deduplication, and count aggregation. Pure Python
performs guarded arithmetic on the small aggregated result. The implementation creates no table,
migration, persisted signal, API endpoint, or frontend feature.

## Scientific interpretation and limitations

A high PRR or ROR is a potential reporting signal only. FAERS lacks a reliable exposed-population
denominator, so these values cannot calculate incidence. Underreporting, stimulated reporting,
duplicate submissions, follow-up behavior, missing information, confounding by indication,
concomitant drugs, and product or terminology ambiguity can materially affect results.

REACTION rows are report-level. Pairing every distinct reported drug with every distinct reaction
within a report describes co-reporting and does not assign a reaction to a drug. Results also
reflect only data loaded locally and the latest report version visible at query time. Historical
evaluation still requires an explicit as-of population to prevent future information leakage.
