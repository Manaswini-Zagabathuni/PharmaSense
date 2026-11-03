# Phase 1B verification: FDA FAERS 2023 Q4 ASCII parser

Verified locally on November 3, 2026. Phase 1B stops at immutable acquisition, streaming parsing,
and aggregate quality reporting. It creates no database migration or MySQL records and performs no
signal or AI analysis.

## Official source and preserved artifact

FDA's current landing page links to the AEMS Quarterly Data Extract index. That index identifies
the October-December 2023 ASCII ZIP as posted January 23, 2024 and approximately 69.1 MB.

- Resolved FDA URL: `https://fis.fda.gov/content/Exports/faers_ascii_2023Q4.zip`
- Local ignored path: `data/raw/faers/2023Q4/faers_ascii_2023Q4.zip`
- Exact size: 72,554,591 bytes
- SHA-256: `7e6b72848ed670900eaf78d24983c845f077091f71ffa7b9c310d590faebac62`
- ZIP integrity: all 18 members passed CRC validation
- Git status for raw and processed directories: ignored (`!!`), not tracked

The original ZIP remains unchanged. No other quarter was downloaded.

## Format inspection

The included `Readme.pdf` (8 pages), `ASC_NTS.pdf` (19 pages), and `FAQs.pdf` were text-extracted
for complete review; README pages were also rendered for visual confirmation. The documentation
defines dollar delimiters, case/version semantics, partial dates, drug role codes, collection
relationships, printable ASCII, and duplicate/repeated-row caveats.

Complete byte inspection of every text member found strict 7-bit ASCII, LF-only endings, no CRLF,
no carriage returns, and no quote characters. The relational files use unquoted `$` fields. The
actual lowercase headers normalize to the exact uppercase parser contracts.

Archive members include the six scoped text files, RPSR, DELETE, seven per-table statistical PDFs,
ASC_NTS, FAQ, and README. RPSR and DELETE remain outside the Phase 1B parser. DELETE has a
single-space first line followed by 2,940 identifiers.

Observed documentation discrepancies:

- The actual DEMO header uses `i_f_code`; documentation also uses `I_F_COD` in places.
- The actual header uses `init_fda_dt`; documentation sometimes says `INIT_FDA_DATE`.
- The provisional schema treated `(PRIMARYID, DRUG_SEQ)` as potentially unique. FDA FAQ 53 and
  this archive demonstrate multiple DRUG detail rows per sequence.
- The archive contains PDFs, although older online documentation refers to `.DOC` files.
- QDE supplies only the latest completed version of a case available when the extract is run; it
  is not guaranteed to contain every earlier version received within the quarter.

## Full parser and quality results

Normal run: 52.609 seconds. A final idempotence rerun completed in 50.197 seconds. Both processed the preserved ZIP
directly and used temporary SQLite only for keys and hashes. The second run reported
`json_changed=False` and `markdown_changed=False`.

| Table | Uncompressed bytes | Columns | Source | Accepted | Rejected | Repeated identifier rows | Exact duplicate rows | Invalid relationships |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DEMO | 60,509,503 | 25 | 415,379 | 415,379 | 0 | 0 | 0 | 0 |
| DRUG | 196,015,959 | 20 | 1,920,732 | 1,920,732 | 0 | 185 | 2 | 0 |
| REAC | 56,431,124 | 4 | 1,500,033 | 1,500,033 | 0 | 0 | 22,675 | 0 |
| OUTC | 7,222,238 | 3 | 327,797 | 327,797 | 0 | 0 | 0 | 0 |
| THER | 23,127,073 | 7 | 633,087 | 633,087 | 0 | 0 | 13 | 0 |
| INDI | 53,070,154 | 4 | 1,115,961 | 1,115,961 | 0 | 0 | 286 | 0 |
| **Total** | **396,376,051** |  | **5,912,989** | **5,912,989** | **0** |  |  | **0** |

All inspected role codes and nonempty partial-date fields passed the implemented format checks.
That does not verify the truth or clinical validity of any source value. Missing-value counts are
available per column in the ignored machine-readable and Markdown reports under
`data/processed/faers/2023Q4`.

Repeated identifiers and exact duplicates are reported, not removed. In particular, the 185 DRUG
identifier repetitions are not all errors: FDA documents multiple details for one drug sequence.
No count is interpreted as incidence, causality, or comparative safety.

## Commands and actual results

Official download and integrity:

```bash
mkdir -p data/raw/faers/2023Q4
curl --proto '=https' --location --fail --show-error \
  --output data/raw/faers/2023Q4/faers_ascii_2023Q4.zip.part \
  https://fis.fda.gov/content/Exports/faers_ascii_2023Q4.zip
file data/raw/faers/2023Q4/faers_ascii_2023Q4.zip.part
unzip -t data/raw/faers/2023Q4/faers_ascii_2023Q4.zip.part
shasum -a 256 data/raw/faers/2023Q4/faers_ascii_2023Q4.zip.part
mv data/raw/faers/2023Q4/faers_ascii_2023Q4.zip.part \
  data/raw/faers/2023Q4/faers_ascii_2023Q4.zip
```

Result: valid deflated ZIP; all members `OK`; checksum and size as recorded above.

Inspection included:

```bash
unzip -l data/raw/faers/2023Q4/faers_ascii_2023Q4.zip
unzip -p data/raw/faers/2023Q4/faers_ascii_2023Q4.zip ASCII/DEMO23Q4.txt | sed -n '1p'
pdfinfo /tmp/pharmasense-faers-2023q4.r4elY5/Readme.pdf
pdfinfo /tmp/pharmasense-faers-2023q4.r4elY5/ASC_NTS.pdf
```

Poppler text extraction and PNG rendering used the bundled runtime because `pdftotext` was not on
the default shell `PATH`. A first diagnostic loop accidentally used zsh's reserved `path` variable,
which temporarily hid standard commands inside that subshell; it was rerun with `member_name` and
did not modify data.

Parser runs:

```bash
time .venv/bin/python -m pharmasense.ingestion.faers.cli \
  data/raw/faers/2023Q4/faers_ascii_2023Q4.zip \
  --json-report data/processed/faers/2023Q4/quality-report.json \
  --markdown-report data/processed/faers/2023Q4/quality-report.md
```

First result: `parsed=5912989 accepted=5912989 rejected=0 elapsed_seconds=52.609` and both reports
created. The final repeat produced the same counts, `elapsed_seconds=50.197`, and both `changed`
flags false.

Final repository check:

```bash
PATH=/Users/manaswinizagabathuni/Documents/Projects/PharmaSense/.venv/bin:/Users/manaswinizagabathuni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH make check
```

Result:

- Ruff lint and format checks passed (40 files).
- Strict mypy passed (38 source files).
- Backend: 24 passed, 1 skipped in 173.01 seconds; coverage 94.36%.
- The skip is the pre-existing MySQL integration test because `TEST_DATABASE_URL` was unset.
- Frontend: ESLint and TypeScript passed; Vitest 5 passed with 100% coverage.

An earlier full test run reached only 87.54% coverage and failed the 90% threshold. Additional CLI,
archive-safety, invalid-value, malformed-row, and idempotence tests were added; the final run above
passes. No result from the failed intermediate run is represented as successful.

## Remaining limitations

- RPSR and DELETE require explicit semantics before persistence.
- “Accepted” means structurally parseable, not scientifically correct.
- Missing values can be legitimate or unknown; the parser does not impute them.
- Exact duplicate rows remain preserved and require a documented persistence policy.
- FDA's replacement of unsupported characters with `?` is irreversible at source.
- The integration test is skipped in environments without the ignored archive.
- MySQL persistence, migrations, cross-quarter version resolution, and deletion handling are
  intentionally deferred.
