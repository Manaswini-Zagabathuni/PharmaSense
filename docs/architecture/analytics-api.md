# Read-only analytics API

Bounded drug and reaction autocomplete is exposed through `/api/v1/discovery/drugs` and
`/api/v1/discovery/reactions`. Both require a 2–200 character `q`, accept a `limit` from 1–25, and
return distinct source-derived terms in deterministic order. See
[source-term discovery](source-term-discovery.md) for population, matching, and privacy semantics.

Phase 3A exposes the existing Phase 2 FAERS analytics through versioned FastAPI endpoints. The
HTTP layer validates requests and serializes typed results. It does not reimplement latest-version
selection, presence deduplication, contingency construction, PRR, ROR, confidence intervals, or
prioritization.

All endpoints are read-only and use the configured SQLAlchemy engine. Missing database
configuration returns HTTP 503. Database and internal analytics failures return sanitized HTTP
500 responses without connection strings, credentials, SQL text, or stack traces.

## Scientific interpretation

FAERS reporting patterns do not establish causality, incidence, comparative safety, or clinical
risk. PRR, ROR, confidence intervals, and priority ranks describe statistical reporting patterns
for research investigation only. Reporting bias, underreporting, duplicate submissions, missing
information, concomitant drugs, and confounding can affect every result. PharmaSense is not a
clinical decision-making system.

The API currently includes every preserved FDA drug role code. Reactions are report-level, so a
drug-reaction pair means both were reported in the same resolved report; it does not assign the
reaction to that drug.

## Endpoints

### `GET /api/v1/signals`

Returns only successfully evaluated and prioritized Phase 2D signals.

Query parameters:

| Parameter | Default | Validation | Meaning |
| --- | ---: | --- | --- |
| `limit` | 25 | 1–100 | Maximum returned prioritized signals |
| `minimum_pair_reports` | 3 | positive, bounded integer | Minimum contingency cell `a` |
| `minimum_population` | omitted | positive, bounded integer | Optional resolved analysis-population minimum |
| `minimum_ror_lower_bound` | 1.0 | 0–1,000,000 | Minimum ROR lower-bound criterion |

Candidate contingency aggregates are filtered by count/population in SQL and streamed into the
Phase 2D evaluator. Only the requested top-N results are retained in application memory. Ranking
remains lower-confidence-bound first, then pair count, ROR, PRR, drug name, and reaction term.

An empty result is HTTP 200 with `items: []`; it does not mean that FAERS contains no reports.

### `GET /api/v1/signals/{drug_name}/reactions/{reaction_term}`

Returns the Phase 2D result for one observed pair using default thresholds. This diagnostics
response can represent an observed but statistically ineligible or non-prioritized pair and
includes all explicit metric and eligibility reasons. A pair with `a = 0` returns HTTP 404.

Path components must be URL-encoded, contain at least one character, and be at most 1,000
characters. Drug names containing literal slash path separators may not be addressable through
this Phase 3A path design.

### `GET /api/v1/drugs`

Returns deterministic Phase 2B drug summaries ordered by report count descending and drug name.

| Parameter | Default | Validation |
| --- | ---: | --- |
| `limit` | 50 | 1–200 |
| `offset` | 0 | 0–1,000,000 |

`report_count` counts resolved latest reports containing the source drug-name group;
`case_count` counts distinct longitudinal cases. Under the current one-report-per-resolved-case
population these values are expected to match.

### `GET /api/v1/drugs/{drug_name}/reactions`

Returns the most frequently co-reported reactions using the existing Phase 2B query.
`limit` defaults to 25 and must be between 1 and 100. A missing drug returns HTTP 404. A known drug
with no reaction rows returns HTTP 200 with an empty collection.

## Signal response fields

Signal responses include:

- source drug name and reaction term;
- resolved analysis population;
- contingency cells `a`, `b`, `c`, and `d`;
- PRR and ROR values or explicit undefined reasons;
- ROR confidence level and finite bounds or an explicit undefined reason;
- applied Phase 2D thresholds;
- observed, calculable, evaluable, eligible, and prioritized statuses; and
- eligibility or priority-exclusion reasons.

No SQLAlchemy models, provenance internals, database URLs, or credentials are serialized.

## Error behavior

- HTTP 404: requested drug or drug-reaction pair is not present in the resolved analytics
  population.
- HTTP 422: FastAPI/Pydantic request validation failure.
- HTTP 500: sanitized database or analytics execution failure.
- HTTP 503: database configuration is unavailable.

The existing `/api/v1/health` liveness and `/api/v1/ready` database-readiness behavior is
unchanged.

## Phase 5A historical endpoints

`GET /api/v1/source-snapshots` returns a bounded provenance inventory. It distinguishes an archive
known in `source_artifact`, checkpointed reports from any run, and reports from completed runs.
Storage paths and source URLs are not returned.

`GET /api/v1/historical/signals/{drug_name}/reactions/{reaction_term}` requires inclusive
`start_quarter` and `end_quarter` values in `YYYYQn` form. The range is bounded to 80 quarters.
The response records the exact loaded quarters selected, the population rule, resolved counts,
Phase 2A exclusions, and independent per-quarter signal results. Empty loaded ranges return HTTP
200 with an empty series. See [historical quarter analytics](historical-quarter-analytics.md) for
the population contract and why this is not a historical as-of reconstruction.
