# Source-term discovery

Phase 6B adds bounded, read-only discovery of drug names and reaction terms already present in the
unambiguously resolved latest-report population. It does not add a vocabulary, synonym service, or
clinical recommendation system.

## API

- `GET /api/v1/discovery/drugs?q={text}&limit={n}` searches source `DRUGNAME` values.
- `GET /api/v1/discovery/reactions?q={text}&limit={n}` searches source `PT` reaction values.

`q` is required, trimmed by the API, and must contain 2–200 characters. `limit` defaults to 10 and
must be 1–25. Search is a case-insensitive literal substring match: SQL wildcard characters in user
input are escaped rather than interpreted. Results are distinct and ordered deterministically by
case-insensitive term and then original term. The database applies the result limit.

Both queries reuse the Phase 2A resolved-latest-report CTE. Invalid versions and unresolved maximum
version ties remain excluded. Duplicate source rows collapse only at the discovery-term grain; no
source row is changed or deleted. The response contains only `term`, bounded response metadata, and
research/source-term notices. It never contains report, patient, SQL, connection, or storage data.

## Frontend behavior

Historical Trends and Signal Comparison share an accessible combobox. It waits until two trimmed
characters are present, debounces requests, asks for at most ten suggestions, supports arrow-key and
Enter selection, and exposes loading, no-match, and failure states. A failure does not block the
workspace. Manual text remains valid and editable, so selecting a suggestion is optional.

Suggestions are source-derived spellings as reported to FAERS. They are not normalized concepts,
automatic synonym mappings, validated product identities, or clinical recommendations. React does
not rank, normalize, calculate, or interpret these terms.

## Operational and scientific limits

Substring search with a leading wildcard may become expensive on a much larger corpus even though
the returned rows are bounded. A future measured optimization may introduce a dedicated read-only
search index without changing source semantics. Search coverage is limited to data successfully
loaded into the resolved analysis population, and source spelling variants remain separate.
