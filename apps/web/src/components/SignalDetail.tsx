import { useEffect, useState } from 'react'

import { ApiError, getSignalDetail } from '../api/client'
import type { SignalDetailResponse } from '../api/types'
import { ErrorPanel, LoadingPanel } from './feedback'
import { formatCount, formatRatio, formatReason } from './format'

interface SignalDetailProps {
  drugName: string
  reactionTerm: string
  onClose: () => void
}

type DetailState =
  | { status: 'loading' }
  | { status: 'ready'; data: SignalDetailResponse }
  | { status: 'missing' }
  | { status: 'error'; error: unknown }

export function SignalDetail({ drugName, reactionTerm, onClose }: SignalDetailProps) {
  const [retry, setRetry] = useState(0)
  const [state, setState] = useState<DetailState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    void getSignalDetail(drugName, reactionTerm, controller.signal)
      .then((data) => setState({ status: 'ready', data }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        if (error instanceof ApiError && error.status === 404) setState({ status: 'missing' })
        else setState({ status: 'error', error })
      })
    return () => controller.abort()
  }, [drugName, reactionTerm, retry])

  function retryRequest() {
    setState({ status: 'loading' })
    setRetry((value) => value + 1)
  }

  return (
    <section className="detail-panel" aria-labelledby="signal-detail-title">
      <div className="detail-panel__header">
        <div>
          <p className="eyebrow">Signal detail</p>
          <h2 id="signal-detail-title">
            {drugName} <span aria-hidden="true">/</span> {reactionTerm}
          </h2>
        </div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="Close detail">
          ×
        </button>
      </div>

      {state.status === 'loading' && <LoadingPanel label="Loading signal detail…" />}
      {state.status === 'error' && (
        <ErrorPanel error={state.error} onRetry={retryRequest} />
      )}
      {state.status === 'missing' && (
        <div className="state-panel state-panel--empty" role="status">
          <h3>Pair not observed</h3>
          <p>This pair was not found in the resolved latest-report population.</p>
        </div>
      )}
      {state.status === 'ready' && <SignalDetailContent response={state.data} />}
    </section>
  )
}

function SignalDetailContent({ response }: { response: SignalDetailResponse }) {
  const { signal } = response
  const interval = signal.ror_confidence_interval
  const reasons = signal.ineligibility_reasons

  return (
    <div className="detail-content">
      <div className="status-row" aria-label="Signal evaluation status">
        <span className={`pill ${signal.is_observed ? 'pill--positive' : ''}`}>Observed pair</span>
        <span className={`pill ${signal.statistically_evaluable ? 'pill--positive' : ''}`}>
          {signal.statistically_evaluable ? 'Statistically evaluable' : 'Not evaluable'}
        </span>
        <span className={`pill ${signal.is_prioritized ? 'pill--accent' : ''}`}>
          {signal.is_prioritized ? 'Prioritized' : 'Not prioritized'}
        </span>
      </div>

      <dl className="metric-grid">
        <div>
          <dt>ROR</dt>
          <dd>{formatRatio(signal.ror.value)}</dd>
          <small>{signal.ror.undefined_reason ? formatReason(signal.ror.undefined_reason) : 'Reporting odds ratio'}</small>
        </div>
        <div>
          <dt>ROR confidence interval</dt>
          <dd>
            {interval.lower_bound === null || interval.upper_bound === null
              ? 'Not defined'
              : `${formatRatio(interval.lower_bound)}–${formatRatio(interval.upper_bound)}`}
          </dd>
          <small>{Math.round(interval.confidence_level * 100)}% log-scale interval</small>
        </div>
        <div>
          <dt>PRR</dt>
          <dd>{formatRatio(signal.prr.value)}</dd>
          <small>{signal.prr.undefined_reason ? formatReason(signal.prr.undefined_reason) : 'Proportional reporting ratio'}</small>
        </div>
        <div>
          <dt>Analysis population</dt>
          <dd>{formatCount(signal.analysis_population)}</dd>
          <small>Resolved latest reports</small>
        </div>
      </dl>

      <div>
        <h3>Contingency counts</h3>
        <div className="contingency" role="group" aria-label="Two by two contingency counts">
          <div><span>a</span><strong>{formatCount(signal.a)}</strong><small>Drug + reaction</small></div>
          <div><span>b</span><strong>{formatCount(signal.b)}</strong><small>Drug, no reaction</small></div>
          <div><span>c</span><strong>{formatCount(signal.c)}</strong><small>Reaction, no drug</small></div>
          <div><span>d</span><strong>{formatCount(signal.d)}</strong><small>Neither</small></div>
        </div>
      </div>

      {(reasons.length > 0 || signal.priority_exclusion_reason) && (
        <div className="diagnostic">
          <h3>Evaluation notes</h3>
          <ul>
            {reasons.map((reason) => <li key={reason}>{formatReason(reason)}</li>)}
            {signal.priority_exclusion_reason && <li>{formatReason(signal.priority_exclusion_reason)}</li>}
          </ul>
        </div>
      )}

      <p className="inline-notice">{response.research_notice}</p>
    </div>
  )
}
