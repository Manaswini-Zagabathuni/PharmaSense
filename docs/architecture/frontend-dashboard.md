# Read-only analytics dashboard

Phase 3B replaces the Phase 0 frontend shell with a responsive React and TypeScript research
dashboard. It consumes the Phase 3A API and performs no latest-version selection, aggregation,
PRR, ROR, confidence-interval calculation, eligibility decision, or ranking in the browser.

## Frontend structure

- `src/api/types.ts` mirrors the public Phase 3A Pydantic response fields.
- `src/api/client.ts` owns the API base URL, query construction, safe path encoding, JSON requests,
  and centralized sanitized errors.
- `src/components/SignalExplorer.tsx` requests and displays prioritized signals and supported
  threshold controls.
- `src/components/SignalDetail.tsx` displays API-provided metrics, confidence bounds,
  contingency counts, and diagnostic statuses for one observed pair.
- `src/components/DrugExplorer.tsx` provides bounded drug pagination and co-reported reaction
  profiles.
- `src/App.tsx` provides accessible workspace navigation and the persistent research-use notice.

React component state is sufficient for these two workspaces, so Phase 3B adds no router or global
state-management dependency. HTTP concerns remain outside presentation components.

## API configuration

The client uses `VITE_API_BASE_URL`, defaulting to `/api/v1`. In local Vite development, requests
under `/api` are proxied to `VITE_API_PROXY_TARGET`, defaulting to `http://localhost:8000`.
Docker Compose sets the proxy target to the internal `api:8000` service.

For the normal local stack:

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:5173>. For independently running processes, start the API on port 8000 and
run:

```bash
pnpm --dir apps/web dev
```

Only a public base path belongs in `VITE_API_BASE_URL`; frontend environment variables are bundled
into browser code and must never contain credentials or secrets.

## Workspaces

### Signal Explorer

The default workspace calls `GET /api/v1/signals` with bounded result, minimum pair-report, and
minimum ROR lower-bound controls. It displays only the returned prioritized results: drug,
reaction, ROR, ROR interval, PRR, and pair-report count. Selecting a row safely URL-encodes the
source values and requests the existing signal-detail endpoint.

Detail results can be observed but ineligible or non-prioritized. The view presents the API's
status flags, metric undefined reasons, interval, complete `a/b/c/d` table, analysis population,
and threshold diagnostics without recalculation.

### Drug Explorer

The drug workspace calls `GET /api/v1/drugs` with a fixed bounded page size of 25 and API `offset`
pagination. Selecting a drug requests its top 25 co-reported reaction terms. Missing drugs, known
drugs without reaction terms, trailing empty pages, and service failures have distinct states.

## Accessibility and resilience

The dashboard uses semantic headings, navigation, forms, tables, labels, status/alert roles,
visible focus styles, keyboard-operable controls, responsive layouts, and reduced-motion styling.
Every data surface includes loading, empty, and sanitized error behavior. HTTP 503 and network
failures are described as service unavailability rather than exposing internal backend details.

Frontend tests mock `fetch` at the API boundary and require no live API or database. They verify
safe encoding, successful rendering, diagnostics, failure/retry behavior, empty states,
pagination, and navigation.

## Scientific boundaries

The research-use banner remains visible across both workspaces. FAERS has substantial limitations;
statistical signals and co-reported events do not establish causality, incidence, comparative
safety, or a drug-specific adverse-event relationship. The dashboard is for research exploration,
not clinical decision-making. It does not add causal language, risk estimates, or clinical advice.

Phase 3B has no authentication because the existing stack is local-only. A public deployment must
add the identity, authorization, rate-limiting, and deployment controls already deferred in the
architecture overview.
