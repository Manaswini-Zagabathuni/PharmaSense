# FAERS statistical signal prioritization and confidence analytics

Phase 2D adds a transparent, read-only prioritization layer above the Phase 2C contingency and
disproportionality calculations. Its purpose is to order statistically evaluable reporting
signals for research review. A priority position is not evidence that a drug caused a reaction,
does not establish a drug safety risk, and is not a clinical recommendation.

## Population and counting rules

Phase 2D does not define another analysis population. It consumes the Phase 2C contingency query,
which uses the Phase 2B deduplicated presence grains over the Phase 2A unambiguously resolved
latest report versions. Invalid-only versions and version ties remain excluded. Each resolved
report contributes at most once to `a`, `b`, `c`, or `d` for a given drug-reaction pair.

The contingency cells retain their Phase 2C definitions:

- `a`: reports containing both the drug and reaction;
- `b`: reports containing the drug but not the reaction;
- `c`: reports containing the reaction but not the drug; and
- `d`: reports containing neither.

The population is `N = a + b + c + d`. Phase 2D uses the existing uncorrected PRR and ROR point
estimates and does not change their formulas or undefined-result behavior.

## ROR confidence interval

When all four cells are positive, the default two-sided 95% ROR confidence interval uses the
standard normal approximation on the log scale:

```text
log(ROR) = log(a) + log(d) - log(b) - log(c)
SE[log(ROR)] = sqrt(1/a + 1/b + 1/c + 1/d)
CI = exp(log(ROR) ± z(1 - alpha/2) × SE[log(ROR)])
```

The confidence level is configurable and must be strictly between zero and one. No
Haldane–Anscombe or other continuity correction is applied. An empty population, any zero cell,
or a non-finite calculation produces no bounds and a stable `UndefinedMetricReason`; the code
never presents infinity as a usable confidence bound. Invalid or impossible contingency counts
are rejected by the existing validated `ContingencyTable`.

This asymptotic interval may be unreliable with sparse counts even when it is mathematically
defined. It is an uncertainty aid, not a hypothesis test or multiple-comparison adjustment.

## Thresholds and typed status

`SignalThresholds` validates three explicit settings:

- `minimum_pair_reports`, default `3` and always required to be positive;
- `minimum_population`, optional and positive when supplied; and
- `minimum_ror_lower_bound`, default `1.0` and finite/non-negative.

`signal_candidate_contingencies_statement()` wraps the Phase 2C observed-pair statement and
applies the pair-count and optional population thresholds in SQL. This reduces data transfer and
avoids one query per pair. Confidence intervals and guarded arithmetic remain pure Python over
the aggregated rows.

`SignalResult` preserves names, population, all four cells, PRR, ROR, confidence bounds,
thresholds, and explicit status fields. The statuses are intentionally distinct:

1. **Observed:** `a > 0`.
2. **Metrics calculable:** both PRR and ROR are finite and defined.
3. **Statistically evaluable:** the metrics and ROR interval are defined.
4. **Eligible for prioritization:** evaluable and all count/population thresholds pass.
5. **Prioritized:** eligible and the ROR lower confidence bound is strictly greater than the
   configured lower-bound minimum.

Ineligible results retain all applicable `SignalEligibilityReason` values. An eligible but
non-prioritized result records that its lower bound did not exceed the minimum. Insufficient
support is therefore visible rather than being converted into a weak or strong signal label.

## Ranking method

`rank_prioritized_signals()` includes only results marked prioritized and sorts them by:

1. ROR lower confidence bound, descending;
2. pair report count `a`, descending;
3. ROR point estimate, descending;
4. PRR point estimate, descending;
5. drug name, ascending; and
6. reaction term, ascending.

This is a lexicographic rule, not a weighted or machine-learning score. Giving the conservative
lower confidence bound first favors evidence whose estimated lower limit remains strongest;
counts and point estimates resolve subsequent ties. Source-name tie-breakers make results
deterministic under the same Python string values. Database collation still controls upstream
source-value grouping.

## Scientific boundaries and limitations

FAERS reports are spontaneous reports and are not proof of causality. Signal prioritization does
not establish drug safety risks, comparative safety, or clinical importance. FAERS lacks a
reliable exposure denominator, so PRR, ROR, confidence intervals, and ranks cannot estimate
incidence rates.

Reporting bias, underreporting, stimulated reporting, incomplete or missing data, duplicate
submissions, follow-up behavior, confounding by indication, concomitant medications, and product
or terminology ambiguity remain possible. Version resolution reduces follow-up duplication but
does not identify all duplicate real-world events or submissions.

All preserved drug role codes currently enter the same drug-presence calculation, including
suspect, concomitant, and interacting roles. Report-level reactions are paired with every distinct
reported drug in the report, which represents co-reporting rather than a drug-specific causal
assignment. No role-specific analysis, exact sparse-data interval, significance test, multiplicity
control, temporal as-of analysis, or clinical review workflow is implemented in Phase 2D.
