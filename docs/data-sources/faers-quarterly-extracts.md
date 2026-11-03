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

## Verified Phase 1B pilot

**2023 Q4 ASCII ZIP**, posted by FDA on January 23, 2024, is the single-quarter pilot.
FDA lists it as a 69.1 MB ASCII archive and also offers a 140 MB XML archive. ASCII is selected
because its separate relational files map directly to the proposed schema, are streamable, and
avoid holding a large XML document in memory.

This quarter is suitable because it uses the mature post-2012 case/version format, predates the
FAERS-to-AEMS platform transition, and sits immediately before a documented population boundary:
starting with 2024 Q1, FDA excludes postmarket study safety reports for unapproved investigational
drugs from the QDE and dashboard. Choosing 2023 Q4 avoids using the transition quarter as a parser
test. It does **not** make 2023 Q4 representative of later populations; the 2024 Q1 exclusion must
be retained as an era annotation in future longitudinal work.

Phase 1B downloaded only this archive from FDA's resolved URL:
`https://fis.fda.gov/content/Exports/faers_ascii_2023Q4.zip`. The preserved ZIP is 72,554,591
bytes with SHA-256
`7e6b72848ed670900eaf78d24983c845f077091f71ffa7b9c310d590faebac62`. It lives under the
ignored `data/raw/faers/2023Q4` path and must never be committed. The committed aggregate manifest
is [faers-2023q4-ascii.json](manifests/faers-2023q4-ascii.json).

## Verified archive format

The ZIP passed a complete CRC test and contains 18 members: six scoped data files, RPSR, a deleted
case list, seven per-table statistical PDFs, `ASC_NTS.pdf`, `FAQs.pdf`, and `Readme.pdf`.

Exact inventory:

- `ASCII/ASC_NTS.pdf`, `FAQs.pdf`, and `Readme.pdf`
- `ASCII/DEMO23Q4.txt` and `.pdf`
- `ASCII/DRUG23Q4.txt` and `.pdf`
- `ASCII/INDI23Q4.txt` and `.pdf`
- `ASCII/OUTC23Q4.txt` and `.pdf`
- `ASCII/REAC23Q4.txt` and `.pdf`
- `ASCII/RPSR23Q4.txt` and `.pdf`
- `ASCII/THER23Q4.txt` and `.pdf`
- `Deleted/DELETE23Q4.txt`

For all eight text members, a complete byte scan verified:

- printable 7-bit ASCII only (therefore valid UTF-8 as a subset);
- LF (`0x0A`) line endings, with no carriage returns;
- dollar-sign delimiters in the seven relational data tables;
- no quote characters and no quoting/escaping convention in use;
- one lowercase header row in each relational file;
- the delete list has a single-space first line rather than a named header.

FDA's included FAQ says modern QDE output permits printable ASCII, LF, and CR and replaces
unapproved characters with `?`. The parser nevertheless verifies the observed archive and flags
non-ASCII bytes rather than silently replacing them.

The six scoped files contain 5,912,989 source rows in total: DEMO 415,379; DRUG 1,920,732; REAC
1,500,033; OUTC 327,797; THER 633,087; and INDI 1,115,961. RPSR and DELETE are inventoried but
not parsed in Phase 1B. The delete list contains 2,940 identifiers after its leading blank-like
line; deletion semantics must be designed before later persistence.

Verified scoped headers:

| File | Actual columns, in order |
| --- | --- |
| DEMO | `primaryid`, `caseid`, `caseversion`, `i_f_code`, `event_dt`, `mfr_dt`, `init_fda_dt`, `fda_dt`, `rept_cod`, `auth_num`, `mfr_num`, `mfr_sndr`, `lit_ref`, `age`, `age_cod`, `age_grp`, `sex`, `e_sub`, `wt`, `wt_cod`, `rept_dt`, `to_mfr`, `occp_cod`, `reporter_country`, `occr_country` |
| DRUG | `primaryid`, `caseid`, `drug_seq`, `role_cod`, `drugname`, `prod_ai`, `val_vbm`, `route`, `dose_vbm`, `cum_dose_chr`, `cum_dose_unit`, `dechal`, `rechal`, `lot_num`, `exp_dt`, `nda_num`, `dose_amt`, `dose_unit`, `dose_form`, `dose_freq` |
| REAC | `primaryid`, `caseid`, `pt`, `drug_rec_act` |
| OUTC | `primaryid`, `caseid`, `outc_cod` |
| THER | `primaryid`, `caseid`, `dsg_drug_seq`, `start_dt`, `end_dt`, `dur`, `dur_cod` |
| INDI | `primaryid`, `caseid`, `indi_drug_seq`, `indi_pt` |

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

Every child also carries `CASEID`. The parser validates that it agrees with the parent, but uses
`PRIMARYID`—and the drug sequence where applicable—for joins. Source row order is retained because
repeated values are not assumed to be accidental duplicates.

FDA's April 2023 FAQ corrects an important provisional assumption: since 2021 Q4, a direct report
may contain multiple DRUG rows with the same `(PRIMARYID, DRUG_SEQ)` for different dosing, route,
or frequency details. The 2023 Q4 archive has 185 rows beyond the first for repeated drug-sequence
identifiers, only two of which are exact duplicate rows. Therefore, that pair is a relationship
key, not a unique row key. THER can also contain multiple intervals per drug sequence, and INDI can
contain multiple terms per drug sequence.

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

The included README, ASC_NTS, and FAQ were inspected as the quarter-specific authorities. Minor
documentation inconsistencies remain: descriptive text uses `I_F_COD` and sometimes
`INIT_FDA_DATE`, while the actual DEMO header contains `i_f_code` and `init_fda_dt`. Parser
contracts follow the actual header and record these discrepancies rather than rewriting values.
