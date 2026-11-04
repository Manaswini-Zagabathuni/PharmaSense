# FAERS drug-reaction analytics foundation

Phase 2B adds read-only, composable SQLAlchemy statements for drug and drug-reaction reporting
summaries. It reuses the Phase 2A latest-version statement as its only population selector. Cases
with invalid-only `CASEVERSION` values or a tied maximum version are therefore absent from every
Phase 2B result.

No source rows are changed, deleted, merged, or normalized. These summaries describe reports in
FAERS; they do not estimate incidence, establish causality, or show that a particular drug caused
a reported reaction.

## Population and intermediate grains

The query layer applies three explicit grains before aggregation:

1. **Resolved population:** one unambiguously resolved latest `(PRIMARYID, CASEID)` selected by
   `latest_report_versions_statement()`.
2. **Drug presence:** one row per `(PRIMARYID, CASEID, drug name)` using the original
   `faers_drug.drugname` value and database equality semantics.
3. **Reaction presence:** one row per `(PRIMARYID, CASEID, reaction term)` using the original
   `faers_reaction.pt` value and database equality semantics.

Drug-reaction presence joins the already-distinct drug and reaction grains within the same report,
producing one row per `(PRIMARYID, CASEID, drug name, reaction term)`. This is an intentional
report-level co-occurrence: REAC is report-level and does not identify which reported drug caused
or is otherwise specifically associated with a reaction.

## Counting rules

`drug_summary_statement()` returns:

- `drug_name`: the preserved source drug-name value representing the database group;
- `report_count`: resolved latest report versions containing that name at least once; and
- `case_count`: distinct longitudinal cases containing that name.

`drug_reaction_summary_statement()` returns the source drug name and reaction term plus the number
of resolved latest reports and distinct cases containing that co-reporting pair.
`most_reported_reactions_for_drug_statement()` applies a parameterized drug-name filter to
the same pair summary and orders it by report count descending, then deterministic lexical
tie-breakers. An optional positive limit can bound the result.

Because Phase 2B admits exactly one latest report per resolved case, `report_count` and
`case_count` are expected to be equal in these queries today. Both are returned deliberately so
their different semantic grains remain visible and future explicitly versioned or longitudinal
analyses do not substitute one metric for the other.

## Duplicate handling and multiplication prevention

Repeated source rows are immutable and remain stored. For presence-based counts, duplicate
drug names or reaction terms within one report contribute once. The query performs this
deduplication before joining the drug and reaction collections, so two repeated drug rows and
three repeated reaction rows cannot inflate one co-reporting pair to six.

No application-level normalization is applied. Database collation controls equality, including
whether case or accents compare equally; whitespace, spelling, brand/generic names, and terminology
variants otherwise remain separate. A report with two different names for the same product may
therefore contribute to two drug-name groups. Deployments must keep collation consistent for
reproducible grouping.

## Interfaces and boundaries

`pharmasense.analytics.drug_reactions` exposes three SQLAlchemy `Select` builders:

- `drug_summary_statement()`
- `drug_reaction_summary_statement()`
- `most_reported_reactions_for_drug_statement(drug_name, limit=None)`

The statements remain transport-independent and composable. Phase 2B adds no API route, schema
table, migration, persisted aggregate, statistical signal calculation, or user interface.

## Limitations

- Results reflect only FAERS cases loaded into the local database and their latest version at
  query time; they are not a complete measure of exposure or event frequency in a population.
- Historical/as-of analysis still requires restricting eligible source snapshots before version
  resolution.
- Unnormalized source values fragment drug concepts and reaction spelling variants until a separately
  reviewed normalization phase exists.
- Joining report-level reactions to every distinct drug in a report represents co-reporting only.
- Query-time version parsing and distinct aggregation must be profiled on larger multi-quarter
  datasets before production scaling decisions are made.
