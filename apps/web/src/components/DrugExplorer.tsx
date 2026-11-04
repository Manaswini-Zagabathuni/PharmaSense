import { useEffect, useState } from 'react'

import { ApiError, getDrugReactions, getDrugs } from '../api/client'
import type { DrugListResponse, DrugReactionListResponse } from '../api/types'
import { EmptyPanel, ErrorPanel, LoadingPanel } from './feedback'
import { formatCount } from './format'

const PAGE_SIZE = 25

type DrugState =
  | { status: 'loading' }
  | { status: 'ready'; data: DrugListResponse }
  | { status: 'error'; error: unknown }

export function DrugExplorer() {
  const [offset, setOffset] = useState(0)
  const [retry, setRetry] = useState(0)
  const [state, setState] = useState<DrugState>({ status: 'loading' })
  const [selectedDrug, setSelectedDrug] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void getDrugs(PAGE_SIZE, offset, controller.signal)
      .then((data) => setState({ status: 'ready', data }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState({ status: 'error', error })
      })
    return () => controller.abort()
  }, [offset, retry])

  function retryRequest() {
    setState({ status: 'loading' })
    setRetry((value) => value + 1)
  }

  function changePage(nextOffset: number) {
    setState({ status: 'loading' })
    setSelectedDrug(null)
    setOffset(nextOffset)
  }

  return (
    <section className="workspace" aria-labelledby="drugs-title">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">Resolved reports</p>
          <h1 id="drugs-title">Drug Explorer</h1>
          <p>Browse source drug-name groups and inspect their most frequently co-reported terms.</p>
        </div>
        <div className="phase-badge">One latest report per resolved case</div>
      </div>

      {state.status === 'loading' && <LoadingPanel label="Loading drug summaries…" />}
      {state.status === 'error' && (
        <ErrorPanel error={state.error} onRetry={retryRequest} />
      )}
      {state.status === 'ready' && state.data.items.length === 0 && offset === 0 && (
        <EmptyPanel
          title="No drug summaries are available"
          message="Confirm that the database contains successfully ingested FAERS reports."
        />
      )}
      {state.status === 'ready' && state.data.items.length === 0 && offset > 0 && (
        <div className="empty-with-action">
          <EmptyPanel
            title="No more drugs on this page"
            message="Return to the previous page to continue browsing."
          />
          <button className="button button--secondary" type="button" onClick={() => changePage(Math.max(0, offset - PAGE_SIZE))}>
            Previous page
          </button>
        </div>
      )}
      {state.status === 'ready' && state.data.items.length > 0 && (
        <div className="results-card">
          <div className="results-card__header">
            <div>
              <p className="eyebrow">Drug summaries</p>
              <h2>Reports {formatCount(offset + 1)}–{formatCount(offset + state.data.items.length)}</h2>
            </div>
            <p className="results-meta">Ordered by resolved report count</p>
          </div>
          <div className="table-scroll">
            <table>
              <thead><tr><th scope="col">Drug</th><th scope="col">Reports</th><th scope="col">Cases</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {state.data.items.map((drug) => (
                  <tr key={drug.drug_name}>
                    <td><strong>{drug.drug_name}</strong></td>
                    <td className="numeric">{formatCount(drug.report_count)}</td>
                    <td className="numeric">{formatCount(drug.case_count)}</td>
                    <td><button className="text-button" type="button" onClick={() => setSelectedDrug(drug.drug_name)}>View reactions</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination" aria-label="Drug pagination">
            <button className="button button--secondary" type="button" disabled={offset === 0} onClick={() => changePage(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
            <span>Page {Math.floor(offset / PAGE_SIZE) + 1}</span>
            <button className="button button--secondary" type="button" disabled={state.data.items.length < PAGE_SIZE} onClick={() => changePage(offset + PAGE_SIZE)}>Next</button>
          </div>
          <p className="inline-notice">{state.data.research_notice}</p>
        </div>
      )}

      {selectedDrug && <DrugReactionPanel key={selectedDrug} drugName={selectedDrug} onClose={() => setSelectedDrug(null)} />}
    </section>
  )
}

type ReactionState =
  | { status: 'loading' }
  | { status: 'ready'; data: DrugReactionListResponse }
  | { status: 'missing' }
  | { status: 'error'; error: unknown }

function DrugReactionPanel({ drugName, onClose }: { drugName: string; onClose: () => void }) {
  const [retry, setRetry] = useState(0)
  const [state, setState] = useState<ReactionState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    void getDrugReactions(drugName, 25, controller.signal)
      .then((data) => setState({ status: 'ready', data }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        if (error instanceof ApiError && error.status === 404) setState({ status: 'missing' })
        else setState({ status: 'error', error })
      })
    return () => controller.abort()
  }, [drugName, retry])

  function retryRequest() {
    setState({ status: 'loading' })
    setRetry((value) => value + 1)
  }

  return (
    <section className="detail-panel" aria-labelledby="drug-reactions-title">
      <div className="detail-panel__header">
        <div><p className="eyebrow">Co-reporting profile</p><h2 id="drug-reactions-title">{drugName}</h2></div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="Close reactions">×</button>
      </div>
      <p className="panel-intro">Reaction terms reported in the same cases as this drug. Co-reporting does not establish causality or a drug-specific adverse-event relationship.</p>
      {state.status === 'loading' && <LoadingPanel label="Loading co-reported reactions…" />}
      {state.status === 'error' && <ErrorPanel error={state.error} onRetry={retryRequest} />}
      {state.status === 'missing' && <EmptyPanel title="Drug not found" message="This drug is not present in the resolved analytics population." />}
      {state.status === 'ready' && state.data.items.length === 0 && <EmptyPanel title="No reactions reported" message="This known drug has no reaction terms in the resolved population." />}
      {state.status === 'ready' && state.data.items.length > 0 && (
        <div className="reaction-list">
          {state.data.items.map((reaction, index) => (
            <div className="reaction-row" key={reaction.reaction_term}>
              <span className="rank">{index + 1}</span>
              <div><strong>{reaction.reaction_term}</strong><small>{formatCount(reaction.report_count)} reports · {formatCount(reaction.case_count)} cases</small></div>
            </div>
          ))}
          <p className="inline-notice">{state.data.research_notice}</p>
        </div>
      )}
    </section>
  )
}
