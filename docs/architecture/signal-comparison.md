# Signal comparison workspace

Phase 6A adds a bounded, read-only Signal Comparison workspace for viewing existing FAERS
drug–reaction signal details side by side. It adds no API route, database query, statistical
formula, persistence model, migration, or ingestion behavior.

## Data flow and bounds

The user enters between two and four explicit source drug-name/reaction-term pairs. The browser:

1. trims required values and rejects incomplete or case-insensitive duplicate pair selections;
2. URL-encodes each pair through the centralized API client;
3. concurrently calls the existing
   `GET /api/v1/signals/{drug_name}/reactions/{reaction_term}` endpoint; and
4. renders results in the original entered order, regardless of response completion order.

The four-pair UI maximum bounds database work without adding a second batch contract or alternate
analytics path. Every request retains existing request IDs, security headers, privacy-conscious
operation timing, sanitized errors, and research-use warnings.

HTTP 404 is represented as an explicit unobserved pair. Network, availability, and server errors
fail the comparison as a unit and can be retried. Retry repeats the same bounded submitted
selection. No partial response is presented as a complete successful comparison.

## Display contract

For each observed pair, the workspace displays fields supplied by `SignalDetailResponse`:

- source drug and reaction terms;
- pair-report cell `a` and analysis population;
- PRR and ROR values;
- ROR confidence interval;
- observed, statistically evaluable, eligible, and prioritized states; and
- metric, eligibility, interval, and priority-exclusion diagnostics.

Undefined estimates remain `Not defined` and retain their server diagnostic. Missing pairs do not
receive zero placeholders. The cards are intentionally not sorted by magnitude and do not produce
a winner, relative-risk statement, composite score, or cross-pair ranking.

## Accessibility and resilience

Each pair is entered in a labeled `fieldset`; add, remove, submit, and retry actions are native
buttons. Validation and failure states use alerts, loading uses a live status region, and results
use labeled semantic articles with text status chips. The responsive grid becomes a single-column
layout when space is limited. Color supplements but never replaces status text.

Frontend tests mock only the API boundary and cover bounded inputs, duplicate validation,
deterministic ordering, observed and unobserved pairs, undefined metrics, complete failure/retry,
and primary navigation.

## Scientific limitations

Side-by-side display is not a comparative safety analysis. FAERS is affected by reporting bias,
underreporting, duplicates, confounding, missing information, and concomitant drugs. PRR and ROR
measure reporting disproportionality and do not establish causality or incidence. Confidence
intervals and prioritization are research aids, not clinical risk estimates, treatment advice, or
evidence that one pair is safer or more important than another.
