# FDA FAERS/AEMS quarterly extracts

## Verified official source and formats

The authoritative bulk-download index is FDA's
[AEMS Quarterly Data Extract (QDE) page](https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html).
FDA describes these as raw, non-cumulative quarterly extracts and currently lists a ZIP in both
ASCII and XML for each quarter. The same page still contains older wording that says “SGML”; the
actual per-quarter links and FDA's
[FAERS QDE documentation](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/faers-quarterly-data-files-documentation)
identify XML and ASCII. PharmaSense will record the actual archive format rather than infer it
from the page's introductory prose.

The documentation explains the September 2012 change from legacy ISR-based AERS extracts to
case/version-based FAERS extracts. This design targets modern extracts beginning with 2012 Q4;
legacy AERS requires a separate adapter and is out of scope for the first ingestion.

The public dashboard and program are now named AEMS. FDA states that FAERS data moved to AEMS on
March 11, 2026. The source-system era (`AERS`, `FAERS`, or `AEMS`) is therefore metadata, not a
reason to rewrite historical source identifiers.

## Selected Phase 1B pilot

**2023 Q4 ASCII ZIP**, posted by FDA on January 23, 2024, is the proposed single-quarter pilot.
FDA lists it as a 69.1 MB ASCII archive and also offers a 140 MB XML archive. ASCII is selected
because its separate relational files map directly to the proposed schema, are streamable, and
avoid holding a large XML document in memory.

This quarter is suitable because it uses the mature post-2012 case/version format, predates the
FAERS-to-AEMS platform transition, and sits immediately before a documented population boundary:
starting with 2024 Q1, FDA excludes postmarket study safety reports for unapproved investigational
drugs from the QDE and dashboard. Choosing 2023 Q4 avoids using the transition quarter as a parser
test. It does **not** make 2023 Q4 representative of later populations; the 2024 Q1 exclusion must
be retained as an era annotation in future longitudinal work.

No archive was downloaded in Phase 1A. Before a Phase 1B download, the implementation must record
the final resolved FDA URL and posted date, stream into a temporary file, calculate SHA-256,
validate the ZIP and expected members, and then atomically promote it to immutable raw storage.

## Scoped ASCII files and relationships

The filenames carry a quarter suffix (for example, `DEMO23Q4`); matching is case-insensitive and
must be based on an allowlist, not arbitrary archive paths.

| File | Grain | Relationship |
| --- | --- | --- |
| DEMO | One demographic/administrative row per report version | `PRIMARYID` identifies a report version; `CASEID` groups follow-ups of the same case |
| DRUG | One reported drug row per report version and drug sequence | Child of DEMO on `PRIMARYID`; `DRUG_SEQ` identifies the drug within that version |
| REAC | One reported reaction term row | Child of DEMO on `PRIMARYID`; the reaction is report-level, not assigned to one drug |
| OUTC | One reported outcome code row | Child of DEMO on `PRIMARYID` |
| THER | One reported therapy interval/detail row | Child of DRUG on (`PRIMARYID`, `DSG_DRUG_SEQ` = `DRUG_SEQ`) |
| INDI | One reported indication term row | Child of DRUG on (`PRIMARYID`, `INDI_DRUG_SEQ` = `DRUG_SEQ`) |

Every child also carries `CASEID`. The loader validates that it agrees with the parent, but uses
`PRIMARYID`—and the drug sequence where applicable—for joins. Source row order is retained because
repeated values are not assumed to be accidental duplicates.

`ROLE_COD` is preserved verbatim on DRUG. A reviewed code lookup may provide labels such as
primary suspect, secondary suspect, concomitant, or interacting, but an unknown code is never
silently coerced. `DRUGNAME` and `INDI_PT` are retained exactly as decoded; REAC `PT` is retained
as the reported/coded preferred-term text. Normalized products and licensed terminology
hierarchies will live in separate, versioned mappings.

## Source limitations and boundaries

- Reports can be incomplete, unverified, duplicated, influenced by publicity, and submitted as
  later follow-ups. A report does not establish that a drug caused an event.
- The files do not supply an exposure denominator and cannot estimate incidence, prevalence, or
  comparative safety.
- Public quarterly data omit case narratives; FDA explains that redacted narratives require an
  individual case-report request.
- The current AEMS dashboard is near-real-time, whereas the bulk files are quarterly snapshots;
  counts can differ. A dataset identity includes source, quarter, posted/retrieval time, and hash.
- FDA documents database behavior and publication-population changes over time, including the
  2024 Q1 investigational-drug study-report exclusion. Longitudinal analysis must model eras.
- MedDRA text may be present, but redistribution or hierarchy use requires a separate licensing
  review. PharmaSense will not bundle proprietary terminology assets.

This project is research software, not clinical decision support. Findings will be described as
potential reporting signals only, never as causal effects or rates.

## Official references consulted

- [AEMS Quarterly Data Extract Files](https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html)
- [FAERS Quarterly Data Files Documentation](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/faers-quarterly-data-files-documentation)
- [AEMS Public Dashboard FAQ](https://fis.fda.gov/extensions/FPD-FAQ/FPD-FAQ.html)
- [Instructions for Requesting Individual Case Reports](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/instructions-requesting-individual-case-reports)
- [AEMS potential-signal information and system transition dates](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/new-safety-information-or-potential-signals-serious-risks-identified-fda-adverse-event-monitoring)

The README inside the selected archive remains the quarter-specific authority for its exact
columns, delimiter, encoding, and code lists. Phase 1B must compare it with this contract before
accepting any row; this design does not claim that draft 2013 documentation exhaustively defines
all later fields.
