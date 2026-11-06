import { type FormEvent, useEffect, useMemo, useState } from 'react'

import {
  getHistoricalSignal,
  getSourceSnapshots,
  type HistoricalSignalQuery,
} from '../api/client'
import type {
  HistoricalSignalResponse,
  QuarterSignal,
  SourceSnapshotListResponse,
} from '../api/types'
import { EmptyPanel, ErrorPanel, LoadingPanel } from './feedback'
import { formatCount, formatRatio, formatReason } from './format'
import { HistoricalComparison } from './HistoricalComparison'

const SNAPSHOT_LIMIT = 200

type SnapshotState =
  | { status: 'loading' }
  | { status: 'ready'; data: SourceSnapshotListResponse }
  | { status: 'error'; error: unknown }

type HistoricalState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; data: HistoricalSignalResponse }
  | { status: 'error'; error: unknown }

const EMPTY_QUERY: HistoricalSignalQuery = {
  drugName: '',
  reactionTerm: '',
  startQuarter: '',
  endQuarter: '',
}

export function HistoricalTrends() {
  const [snapshotRetry, setSnapshotRetry] = useState(0)
  const [snapshots, setSnapshots] = useState<SnapshotState>({ status: 'loading' })
  const [draft, setDraft] = useState<HistoricalSignalQuery>(EMPTY_QUERY)
  const [submitted, setSubmitted] = useState<HistoricalSignalQuery | null>(null)
  const [historicalRetry, setHistoricalRetry] = useState(0)
  const [historical, setHistorical] = useState<HistoricalState>({ status: 'idle' })
  const [validationMessage, setValidationMessage] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void getSourceSnapshots(SNAPSHOT_LIMIT, controller.signal)
      .then((data) => setSnapshots({ status: 'ready', data }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setSnapshots({ status: 'error', error })
      })
    return () => controller.abort()
  }, [snapshotRetry])

  const loadedQuarters = useMemo(() => {
    if (snapshots.status !== 'ready') return []
    return Array.from(
      new Set(
        snapshots.data.items
          .filter((snapshot) => snapshot.contains_successfully_loaded_reports)
          .map((snapshot) => snapshot.source_quarter),
      ),
    ).sort()
  }, [snapshots])

  useEffect(() => {
    if (submitted === null) return
    const controller = new AbortController()
    void getHistoricalSignal(submitted, controller.signal)
      .then((data) => setHistorical({ status: 'ready', data }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setHistorical({ status: 'error', error })
      })
    return () => controller.abort()
  }, [submitted, historicalRetry])

  function submitHistoricalQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const query = {
      ...draft,
      drugName: draft.drugName.trim(),
      reactionTerm: draft.reactionTerm.trim(),
      startQuarter: draft.startQuarter || loadedQuarters[0] || '',
      endQuarter: draft.endQuarter || loadedQuarters.at(-1) || '',
    }
    if (!query.drugName || !query.reactionTerm) {
      setValidationMessage('Enter both a drug name and a reaction term.')
      return
    }
    if (!query.startQuarter || !query.endQuarter) {
      setValidationMessage('Choose both a start quarter and an end quarter.')
      return
    }
    if (loadedQuarters.indexOf(query.startQuarter) > loadedQuarters.indexOf(query.endQuarter)) {
      setValidationMessage('The start quarter must not follow the end quarter.')
      return
    }

    setValidationMessage(null)
    setHistorical({ status: 'loading' })
    setSubmitted(query)
    setHistoricalRetry((value) => value + 1)
  }

  function retrySnapshots() {
    setSnapshots({ status: 'loading' })
    setSnapshotRetry((value) => value + 1)
  }

  function retryHistorical() {
    setHistorical({ status: 'loading' })
    setHistoricalRetry((value) => value + 1)
  }

  return (
    <section className="workspace" aria-labelledby="historical-title">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">Loaded source quarters</p>
          <h1 id="historical-title">Historical Trends</h1>
          <p>
            Compare API-provided reporting measurements for a drug–reaction pair across completed
            FAERS source-quarter ingestions.
          </p>
        </div>
        <div className="phase-badge">Phase 5B · Server-calculated</div>
      </div>

      {snapshots.status === 'loading' && <LoadingPanel label="Loading source-quarter inventory…" />}
      {snapshots.status === 'error' && (
        <ErrorPanel
          error={snapshots.error}
          onRetry={retrySnapshots}
          title="Unable to load source quarters"
        />
      )}
      {snapshots.status === 'ready' && loadedQuarters.length === 0 && (
        <EmptyPanel
          title="No completed source quarters are available"
          message="A source archive may be known in provenance without containing reports from a completed ingestion."
        />
      )}
      {snapshots.status === 'ready' && loadedQuarters.length > 0 && (
        <>
          <form
            className="filter-bar historical-filter"
            onSubmit={submitHistoricalQuery}
            aria-label="Historical signal selection"
            noValidate
          >
            <label>
              Drug name
              <input
                value={draft.drugName}
                onChange={(event) => setDraft({ ...draft, drugName: event.target.value })}
                autoComplete="off"
                required
              />
            </label>
            <label>
              Reaction term
              <input
                value={draft.reactionTerm}
                onChange={(event) => setDraft({ ...draft, reactionTerm: event.target.value })}
                autoComplete="off"
                required
              />
            </label>
            <label>
              Start quarter
              <select
                value={draft.startQuarter || loadedQuarters[0] || ''}
                onChange={(event) => setDraft({ ...draft, startQuarter: event.target.value })}
                required
              >
                {loadedQuarters.map((quarter) => (
                  <option value={quarter} key={quarter}>{quarter}</option>
                ))}
              </select>
            </label>
            <label>
              End quarter
              <select
                value={draft.endQuarter || loadedQuarters.at(-1) || ''}
                onChange={(event) => setDraft({ ...draft, endQuarter: event.target.value })}
                required
              >
                {loadedQuarters.map((quarter) => (
                  <option value={quarter} key={quarter}>{quarter}</option>
                ))}
              </select>
            </label>
            <button className="button button--primary" type="submit">
              Analyze history
            </button>
          </form>

          {validationMessage && (
            <p className="validation-message" role="alert">{validationMessage}</p>
          )}

          {historical.status === 'idle' && (
            <div className="state-panel state-panel--empty historical-initial-state">
              <p className="state-kicker">Start an analysis</p>
              <h3>Choose a drug–reaction pair</h3>
              <p>The API will resolve and evaluate the pair independently in each loaded quarter.</p>
            </div>
          )}
          {historical.status === 'loading' && (
            <LoadingPanel label="Loading historical reporting measurements…" />
          )}
          {historical.status === 'error' && (
            <ErrorPanel
              error={historical.error}
              onRetry={retryHistorical}
              title="Unable to load historical results"
            />
          )}
          {historical.status === 'ready' && historical.data.items.length === 0 && (
            <EmptyPanel
              title="No loaded quarters matched this range"
              message="The API returned no historical measurements for the selected completed-source population."
            />
          )}
          {historical.status === 'ready' && historical.data.items.length > 0 && (
            <HistoricalResults response={historical.data} />
          )}

        </>
      )}
      {snapshots.status === 'ready' && (
        <ReproducibilityPanel
          snapshots={snapshots.data}
          historical={historical.status === 'ready' ? historical.data : null}
        />
      )}

      <section className="limitations-card" aria-labelledby="historical-limitations-title">
        <p className="eyebrow">Interpretation boundary</p>
        <h2 id="historical-limitations-title">Research reporting patterns, not clinical risk</h2>
        <p>
          FAERS analyses describe reported associations. PRR and ROR do not establish causality,
          incidence, clinical risk, or treatment recommendations. Quarter comparisons can change
          with reporting behavior, follow-ups, duplicate submissions, underreporting, confounding,
          and terminology changes. Results use loaded source data and are not necessarily a true
          historical as-of reconstruction.
        </p>
      </section>
    </section>
  )
}

function HistoricalResults({ response }: { response: HistoricalSignalResponse }) {
  return (
    <div className="historical-results">
      <HistoricalComparison response={response} />
      <div className="results-card">
        <div className="results-card__header">
          <div>
            <p className="eyebrow">Quarter measurements</p>
            <h2>{formatCount(response.returned_count)} loaded quarters</h2>
          </div>
          <p className="results-meta">Detailed API values</p>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Quarter</th>
                <th scope="col">Population</th>
                <th scope="col">Pair reports</th>
                <th scope="col">PRR</th>
                <th scope="col">ROR</th>
                <th scope="col">ROR confidence interval</th>
                <th scope="col">Status</th>
                <th scope="col">Diagnostics</th>
              </tr>
            </thead>
            <tbody>
              {response.items.map((item) => <HistoricalRow item={item} key={item.source_quarter} />)}
            </tbody>
          </table>
        </div>
        <p className="inline-notice">{response.research_notice}</p>
      </div>
    </div>
  )
}

function HistoricalRow({ item }: { item: QuarterSignal }) {
  const { signal } = item
  const interval = signal.ror_confidence_interval
  const diagnostics = Array.from(
    new Set(
      [
        ...signal.ineligibility_reasons,
        signal.prr.undefined_reason,
        signal.ror.undefined_reason,
        interval.undefined_reason,
        signal.priority_exclusion_reason,
      ].filter((reason): reason is NonNullable<typeof reason> => reason !== null),
    ),
  )
  const status = signal.is_prioritized
    ? 'Prioritized'
    : signal.eligible_for_prioritization
      ? 'Eligible, not prioritized'
      : 'Not eligible'

  return (
    <tr>
      <td><strong>{item.source_quarter}</strong></td>
      <td className="numeric">{formatCount(signal.analysis_population)}</td>
      <td className="numeric">{formatCount(signal.a)}</td>
      <td className="numeric">{formatRatio(signal.prr.value)}</td>
      <td className="numeric">{formatRatio(signal.ror.value)}</td>
      <td className="numeric">
        {interval.lower_bound === null || interval.upper_bound === null
          ? 'Not defined'
          : `${formatRatio(interval.lower_bound)}–${formatRatio(interval.upper_bound)}`}
      </td>
      <td><span className={`pill ${signal.is_prioritized ? 'pill--accent' : ''}`}>{status}</span></td>
      <td>
        {diagnostics.length === 0
          ? 'None'
          : <ul className="compact-list">{diagnostics.map((reason) => <li key={reason}>{formatReason(reason)}</li>)}</ul>}
      </td>
    </tr>
  )
}

function ReproducibilityPanel({
  snapshots,
  historical,
}: {
  snapshots: SourceSnapshotListResponse
  historical: HistoricalSignalResponse | null
}) {
  return (
    <details className="provenance-panel">
      <summary>Source snapshots and reproducibility</summary>
      <div className="provenance-content">
        {historical && (
          <>
            <dl className="summary-grid">
              <div><dt>Requested range</dt><dd>{historical.metadata.requested_start_quarter}–{historical.metadata.requested_end_quarter}</dd></div>
              <div><dt>Selected quarters</dt><dd>{historical.metadata.selected_source_quarters.join(', ') || 'None'}</dd></div>
              <div><dt>Resolved reports</dt><dd>{formatCount(historical.metadata.resolved_report_count)}</dd></div>
              <div><dt>Resolved cases</dt><dd>{formatCount(historical.metadata.resolved_case_count)}</dd></div>
              <div><dt>Invalid-version exclusions</dt><dd>{formatCount(historical.metadata.excluded_invalid_version_case_count)}</dd></div>
              <div><dt>Version-tie exclusions</dt><dd>{formatCount(historical.metadata.excluded_version_tie_case_count)}</dd></div>
            </dl>
            <p className="method-notice">{historical.historical_method_notice}</p>
          </>
        )}
        <div className="table-scroll">
          <table>
            <thead><tr><th scope="col">Quarter</th><th scope="col">Archive</th><th scope="col">Load state</th><th scope="col">Loaded reports</th><th scope="col">Loaded cases</th><th scope="col">SHA-256</th></tr></thead>
            <tbody>
              {snapshots.items.map((snapshot) => (
                <tr key={snapshot.archive_sha256}>
                  <td><strong>{snapshot.source_quarter}</strong></td>
                  <td>{snapshot.filename}</td>
                  <td>{snapshot.contains_successfully_loaded_reports ? 'Completed reports available' : 'Provenance only or incomplete'}</td>
                  <td className="numeric">{formatCount(snapshot.successfully_loaded_report_count)}</td>
                  <td className="numeric">{formatCount(snapshot.successfully_loaded_case_count)}</td>
                  <td><code className="checksum">{snapshot.archive_sha256}</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  )
}
