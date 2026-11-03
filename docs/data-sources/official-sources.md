# Official data sources

Only public sources may enter the PharmaSense research pipeline. Each ingestion adapter must
record the source URL, retrieval time, coverage period, checksum, and parser version.

## FDA adverse-event extracts

The primary adverse-event source is the FDA's quarterly extract page, now presented under the
Adverse Event Monitoring System (AEMS) program and formerly called FAERS. Quarterly archives are
raw, non-cumulative extracts containing report demographics, drugs, reactions, outcomes, and
report-source information.

- [FDA AEMS quarterly data extract files](https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html)
- [FDA quarterly file documentation](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/faers-quarterly-data-files-documentation)

The verified format, 2023 Q4 pilot, format-era boundaries, checksum, and source limitations are
documented in [FAERS/AEMS quarterly extracts](faers-quarterly-extracts.md). The archive is retained
only in ignored local raw storage; Git contains an aggregate manifest, not FDA records.

The bulk archives, not the openFDA API, will be the reproducible analytical baseline.

## Documented FDA safety activity

- [FDA potential-signal quarterly reports](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/new-safety-information-or-potential-signals-serious-risks-identified-fda-adverse-event-monitoring)
- [Drug Safety-related Labeling Changes](https://www.fda.gov/safety/medical-product-safety-information/drug-safety-related-labeling-changes)
- [FDA Drug Safety Communications](https://www.fda.gov/drugs/drug-safety-and-availability/drug-safety-communications)
- [Drugs@FDA](https://www.accessdata.fda.gov/scripts/cder/daf/)

These sources document different kinds of evidence and action. They are not interchangeable or
a complete set of positive and negative labels. SrLC coverage begins in January 2016 and excludes
several product categories; the specific coverage statement must be retained with ingested data.

## Labeling evidence

- [DailyMed REST API](https://dailymed.nlm.nih.gov/dailymed/webservices-help/v2/spls_api.cfm)
- [DailyMed source and disclaimer](https://dailymed.nlm.nih.gov/dailymed/about-dailymed.cfm)

DailyMed provides machine-readable Structured Product Labeling submitted by companies and in
current use. It may differ from the latest FDA-approved label and its contents may not have been
verified by FDA. Drugs@FDA is preferred when FDA approval status or the last approved labeling is
material. Future retrieval responses must show source, label identity, section, and version date.

## Drug normalization

- [NLM RxNorm APIs](https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html)

Approximate RxNorm matches are candidates for review, not authoritative mappings. Original
reported names must always remain available. MedDRA hierarchy assets must not be redistributed
without confirming applicable licensing terms.
