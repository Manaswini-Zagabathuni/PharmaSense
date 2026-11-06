# Reproducible analysis URLs

Phase 6C stores user-selected analytics configuration in the browser URL. It does not store an API
response, calculated metric, source record, patient information, credential, or hidden application
state. No routing dependency is used; PharmaSense relies on `URL`, `URLSearchParams`, and
`history.replaceState`.

## Historical Trends

The supported format is:

```text
/?workspace=historical&drug={source term}&reaction={source term}&start={YYYYQn}&end={YYYYQn}
```

All four analysis parameters must occur exactly once. Terms are trimmed, non-empty, and limited to
the existing API term bound of 1,000 characters. Quarters must match `YYYYQ1` through `YYYYQ4`, the
start must not follow the end, and both quarters must occur in the currently loaded completed-source
inventory. Syntactically valid but unavailable quarters are rejected after that inventory loads.

A valid URL populates the form but does not submit it. An incomplete, duplicated, malformed,
reversed, or unavailable configuration is discarded as a unit. The normal empty form and available
quarter defaults are shown with validation feedback where appropriate.

## Signal Comparison

Pairs use repeated parameters; array order is the comparison order:

```text
/?workspace=comparison&drug={drug 1}&reaction={reaction 1}&drug={drug 2}&reaction={reaction 2}
```

The parser pairs the first drug with the first reaction, and so on. It accepts two through four
complete pairs. Counts must match, terms must be non-empty and no longer than 1,000 characters, and
case-insensitive drug–reaction identities must be unique. Fewer than two, more than four,
incomplete, malformed, or duplicate pairs cause the entire shared comparison configuration to be
discarded. The bounded two-row empty form is then shown. Valid restored pairs remain unsubmitted.

## Synchronization and copying

Selecting a workspace sets its `workspace` parameter. A complete valid form replaces the current
history entry with its canonical configuration URL. Partial or invalid edits retain only the
workspace parameter, so stale valid selections are not accidentally shared. Browser back/forward
workspace changes are observed through `popstate`.

Each supported workspace provides an accessible **Copy analysis link** button. It is disabled until
the current form is valid and reports clipboard success or failure without exposing internal error
details. Clipboard availability and permission remain browser concerns.

These links share configuration, not stored results or a frozen dataset. Reopening a link populates
the form; when the user runs it, the application queries the currently loaded data. Results can
change after data ingestion or other legitimate source-population changes. A link does not prove
scientific reproducibility, causality, incidence, or clinical validity.
