import { type FormEvent, useEffect, useState } from 'react'

import { getSignals, type SignalQuery } from '../api/client'
import type { Signal, SignalListResponse } from '../api/types'
import { EmptyPanel, ErrorPanel, LoadingPanel } from './feedback'
import { formatCount, formatRatio } from './format'
import { SignalDetail } from './SignalDetail'

const DEFAULT_QUERY: SignalQuery = {
  limit: 25,
  minimumPairReports: 3,
  minimumRorLowerBound: 1,
}

type SignalState =
  | { status: 'loading' }
  | { status: 'ready'; data: SignalListResponse }
  | { status: 'error'; error: unknown }

export function SignalExplorer() {
  const [query, setQuery] = useState(DEFAULT_QUERY)
  const [draft, setDraft] = useState(DEFAULT_QUERY)
  const [retry, setRetry] = useState(0)
  const [state, setState] = useState<SignalState>({ status: 'loading' })
  const [selected, setSelected] = useState<Signal | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void getSignals(query, controller.signal)
      .then((data) => setState({ status: 'ready', data }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState({ status: 'error', error })
      })
    return () => controller.abort()
  }, [query, retry])

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setState({ status: 'loading' })
    setSelected(null)
    setQuery(draft)
    setRetry((value) => value + 1)
  }

  function retryRequest() {
    setState({ status: 'loading' })
    setRetry((value) => value + 1)
  }

  return (
    <section className="workspace" aria-labelledby="signals-title">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">Primary workspace</p>
          <h1 id="signals-title">Signal Explorer</h1>
          <p>
            Prioritized drug–reaction reporting patterns ranked by the API-provided lower ROR
            confidence bound.
          </p>
        </div>
        <div className="phase-badge">Phase 3B · Read only</div>
      </div>

      <form className="filter-bar" onSubmit={applyFilters} aria-label="Signal filters">
        <label>
          Results
          <select
            value={draft.limit}
            onChange={(event) => setDraft({ ...draft, limit: Number(event.target.value) })}
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </label>
        <label>
          Minimum pair reports
          <input
            type="number"
            min="1"
            max="9223372036854775807"
            required
            value={draft.minimumPairReports}
            onChange={(event) =>
              setDraft({ ...draft, minimumPairReports: event.target.valueAsNumber })
            }
          />
        </label>
        <label>
          Minimum ROR lower bound
          <input
            type="number"
            min="0"
            max="1000000"
            step="0.1"
            required
            value={draft.minimumRorLowerBound}
            onChange={(event) =>
              setDraft({ ...draft, minimumRorLowerBound: event.target.valueAsNumber })
            }
          />
        </label>
        <button className="button button--primary" type="submit">
          Apply filters
        </button>
      </form>

      {state.status === 'loading' && <LoadingPanel label="Evaluating prioritized signals…" />}
      {state.status === 'error' && (
        <ErrorPanel error={state.error} onRetry={retryRequest} />
      )}
      {state.status === 'ready' && state.data.items.length === 0 && (
        <EmptyPanel
          title="No prioritized signals meet these thresholds"
          message="Try a lower pair-report threshold, or confirm that FAERS data has been ingested."
        />
      )}
      {state.status === 'ready' && state.data.items.length > 0 && (
        <SignalResults response={state.data} onSelect={setSelected} />
      )}

      {selected && (
        <SignalDetail
          key={`${selected.drug_name}\u0000${selected.reaction_term}`}
          drugName={selected.drug_name}
          reactionTerm={selected.reaction_term}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  )
}

function SignalResults({
  response,
  onSelect,
}: {
  response: SignalListResponse
  onSelect: (signal: Signal) => void
}) {
  return (
    <div className="results-card">
      <div className="results-card__header">
        <div>
          <p className="eyebrow">Prioritized results</p>
          <h2>{formatCount(response.returned_count)} reporting patterns</h2>
        </div>
        <p className="results-meta">Showing up to {response.limit}</p>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Drug</th>
              <th scope="col">Reaction</th>
              <th scope="col">ROR</th>
              <th scope="col">95% CI</th>
              <th scope="col">PRR</th>
              <th scope="col">Pair reports</th>
              <th scope="col"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {response.items.map((signal) => (
              <tr key={`${signal.drug_name}\u0000${signal.reaction_term}`}>
                <td><strong>{signal.drug_name}</strong></td>
                <td>{signal.reaction_term}</td>
                <td className="numeric">{formatRatio(signal.ror.value)}</td>
                <td className="numeric">
                  {signal.ror_confidence_interval.lower_bound === null ||
                  signal.ror_confidence_interval.upper_bound === null
                    ? 'Not defined'
                    : `${formatRatio(signal.ror_confidence_interval.lower_bound)}–${formatRatio(signal.ror_confidence_interval.upper_bound)}`}
                </td>
                <td className="numeric">{formatRatio(signal.prr.value)}</td>
                <td className="numeric">{formatCount(signal.a)}</td>
                <td>
                  <button className="text-button" type="button" onClick={() => onSelect(signal)}>
                    Inspect
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="inline-notice">{response.research_notice}</p>
    </div>
  )
}
