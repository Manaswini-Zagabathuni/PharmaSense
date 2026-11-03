# Contributing to PharmaSense

Thank you for helping build PharmaSense responsibly.

## Development workflow

1. Create a focused branch from `main`.
2. Copy `.env.example` to `.env` and replace placeholder passwords.
3. Install the locked dependencies described in the README.
4. Keep ingestion, normalization, statistics, evaluation, and retrieval logic outside HTTP route
   handlers. Routes should validate requests and delegate to application services.
5. Add tests and documentation for behavioral or scientific changes.
6. Run `make check` before opening a pull request.

Do not commit secrets, downloaded FDA archives, generated data, patient data, proprietary
terminology assets, or controlled-workspace exports.

## Scientific language

- Say “potential reporting signal,” not “causal relationship” or “side-effect rate.”
- Preserve raw source values and provenance when adding normalization.
- Document time cutoffs and avoid using future regulatory actions during historical evaluation.
- Never invent records, results, benchmarks, or deployment status.

## Database changes

Create a new Alembic revision for every schema change. Do not edit a migration that may already
have been applied outside your branch. Verify upgrades against a clean MySQL database.

## Security

Use parameterized SQLAlchemy statements, validate external inputs, bound expensive operations,
and avoid logging credentials or sensitive connection details. Report suspected vulnerabilities
privately to the maintainers rather than opening a public issue.
