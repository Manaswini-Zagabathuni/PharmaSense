# Project overview and demo experience

Phase 7A makes the project overview the default browser workspace. It is a static, frontend-only
orientation surface and does not call the API, require a database connection, calculate metrics, or
duplicate any analytics flow.

## Content and navigation

The overview explains PharmaSense as a research-oriented pharmacovigilance analytics platform over
loaded FDA FAERS source data. It presents the implemented capabilities:

- Signal Explorer
- Drug Explorer
- Historical Trends
- Signal Comparison
- Source-Term Discovery
- Reproducible Analysis Links

Capability controls call the same workspace-selection function as the persistent primary
navigation. Signal, drug, historical, and comparison views therefore remain the single
implementations of their respective workflows. The brand and **Overview** navigation control return
to the landing experience.

The workflow narrative—**Discover → Explore → Analyze → Compare → Reproduce**—describes existing
behavior only. It makes no claims about production usage, performance, clinical validation, or
automated scientific interpretation.

## URL behavior

An absent or unrecognized `workspace` query parameter opens the overview. Existing workspaces use
explicit values: `signals`, `drugs`, `historical`, and `comparison`. Historical and comparison
configuration parameters continue to follow the validation rules in
[reproducible analysis URLs](reproducible-analysis-urls.md).

## Scientific and operational boundary

The overview remains useful when the API or MySQL is unavailable because all explanatory content is
local. It prominently states that FAERS is a spontaneous reporting system and that reporting
patterns and disproportionality metrics do not establish causality, incidence, or clinical risk.
PharmaSense remains a research and exploratory analysis tool, not a clinical decision system.

The layout uses existing typography, color, button, focus, and responsive patterns. Semantic
sections, headings, ordered workflow content, labelled navigation, native buttons, visible keyboard
focus, and responsive grids provide the accessibility foundation without a UI framework.
