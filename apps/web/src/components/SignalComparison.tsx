import { type FormEvent, useEffect, useState } from 'react'

import { ApiError, getSignalDetail } from '../api/client'
import type { SignalDetailResponse } from '../api/types'
import { EmptyPanel, ErrorPanel, LoadingPanel } from './feedback'
import { formatCount, formatRatio, formatReason } from './format'
import { SourceTermCombobox } from './SourceTermCombobox'

const MINIMUM_PAIRS = 2
const MAXIMUM_PAIRS = 4

interface PairDraft {
  id: number
  drugName: string
  reactionTerm: string
}

interface PairSelection {
  drugName: string
  reactionTerm: string
}

type PairResult =
  | { selection: PairSelection; status: 'ready'; response: SignalDetailResponse }
  | { selection: PairSelection; status: 'missing' }

type ComparisonState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; results: PairResult[] }
  | { status: 'error'; error: unknown }

const INITIAL_PAIRS: PairDraft[] = [
  { id: 1, drugName: '', reactionTerm: '' },
  { id: 2, drugName: '', reactionTerm: '' },
]

export function SignalComparison() {
  const [pairs, setPairs] = useState(INITIAL_PAIRS)
  const [nextId, setNextId] = useState(3)
  const [submitted, setSubmitted] = useState<PairSelection[] | null>(null)
  const [retry, setRetry] = useState(0)
  const [state, setState] = useState<ComparisonState>({ status: 'idle' })
  const [validationMessage, setValidationMessage] = useState<string | null>(null)

  useEffect(() => {
    if (submitted === null) return
    const controller = new AbortController()
    void Promise.all(
      submitted.map(async (selection): Promise<PairResult> => {
        try {
          const response = await getSignalDetail(
            selection.drugName,
            selection.reactionTerm,
            controller.signal,
          )
          return { selection, status: 'ready', response }
        } catch (error: unknown) {
          if (error instanceof ApiError && error.status === 404) {
            return { selection, status: 'missing' }
          }
          throw error
        }
      }),
    )
      .then((results) => setState({ status: 'ready', results }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState({ status: 'error', error })
      })
    return () => controller.abort()
  }, [submitted, retry])

  function updatePair(id: number, field: 'drugName' | 'reactionTerm', value: string) {
    setPairs((current) =>
      current.map((pair) => (pair.id === id ? { ...pair, [field]: value } : pair)),
    )
  }

  function addPair() {
    if (pairs.length >= MAXIMUM_PAIRS) return
    setPairs((current) => [...current, { id: nextId, drugName: '', reactionTerm: '' }])
    setNextId((value) => value + 1)
  }

  function removePair(id: number) {
    if (pairs.length <= MINIMUM_PAIRS) return
    setPairs((current) => current.filter((pair) => pair.id !== id))
  }

  function submitComparison(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const selections = pairs.map((pair) => ({
      drugName: pair.drugName.trim(),
      reactionTerm: pair.reactionTerm.trim(),
    }))
    if (selections.some((pair) => !pair.drugName || !pair.reactionTerm)) {
      setValidationMessage('Enter both a drug name and reaction term for every pair.')
      return
    }
    const identities = selections.map(
      (pair) => `${pair.drugName.toLowerCase()}\u0000${pair.reactionTerm.toLowerCase()}`,
    )
    if (new Set(identities).size !== identities.length) {
      setValidationMessage('Each selected drug–reaction pair must be unique.')
      return
    }

    setValidationMessage(null)
    setState({ status: 'loading' })
    setSubmitted(selections)
    setRetry((value) => value + 1)
  }

  function retryComparison() {
    setState({ status: 'loading' })
    setRetry((value) => value + 1)
  }

  return (
    <section className="workspace" aria-labelledby="signal-comparison-title">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">Side-by-side evidence</p>
          <h1 id="signal-comparison-title">Signal Comparison</h1>
          <p>
            Compare server-evaluated FAERS reporting measurements for two to four explicitly
            selected observed drug–reaction pairs.
          </p>
        </div>
        <div className="phase-badge">Phase 6A · Read only</div>
      </div>

      <form
        className="comparison-form"
        onSubmit={submitComparison}
        aria-describedby="comparison-form-help"
        noValidate
      >
        <div className="comparison-form__header">
          <div>
            <h2>Pairs to compare</h2>
            <p id="comparison-form-help">
              Source terms are matched through the existing signal-detail API. Comparison order
              follows the order entered below.
            </p>
          </div>
          <span>{pairs.length} of {MAXIMUM_PAIRS} pairs</span>
        </div>
        <div className="pair-fields">
          {pairs.map((pair, index) => (
            <fieldset key={pair.id}>
              <legend>Pair {index + 1}</legend>
              <SourceTermCombobox
                id={`comparison-drug-${pair.id}`}
                label={`Drug name for pair ${index + 1}`}
                kind="drugs"
                value={pair.drugName}
                onChange={(value) => updatePair(pair.id, 'drugName', value)}
              />
              <SourceTermCombobox
                id={`comparison-reaction-${pair.id}`}
                label={`Reaction term for pair ${index + 1}`}
                kind="reactions"
                value={pair.reactionTerm}
                onChange={(value) => updatePair(pair.id, 'reactionTerm', value)}
              />
              {pairs.length > MINIMUM_PAIRS && (
                <button
                  className="text-button"
                  type="button"
                  onClick={() => removePair(pair.id)}
                  aria-label={`Remove pair ${index + 1}`}
                >
                  Remove
                </button>
              )}
            </fieldset>
          ))}
        </div>
        <div className="comparison-form__actions">
          <button
            className="button button--secondary"
            type="button"
            onClick={addPair}
            disabled={pairs.length >= MAXIMUM_PAIRS}
          >
            Add pair
          </button>
          <button className="button button--primary" type="submit">Compare signals</button>
        </div>
      </form>

      {validationMessage && (
        <p className="validation-message" role="alert">{validationMessage}</p>
      )}
      {state.status === 'idle' && (
        <div className="state-panel state-panel--empty comparison-initial-state">
          <p className="state-kicker">Ready to compare</p>
          <h3>Enter at least two distinct pairs</h3>
          <p>PharmaSense will request each pair from the existing read-only signal-detail API.</p>
        </div>
      )}
      {state.status === 'loading' && <LoadingPanel label="Loading signal comparison…" />}
      {state.status === 'error' && (
        <ErrorPanel
          error={state.error}
          onRetry={retryComparison}
          title="Unable to compare signals"
        />
      )}
      {state.status === 'ready' && <ComparisonResults results={state.results} />}

      <section className="limitations-card" aria-labelledby="comparison-limitations-title">
        <p className="eyebrow">Interpretation boundary</p>
        <h2 id="comparison-limitations-title">Reporting disproportionality, not comparative risk</h2>
        <p>
          FAERS is affected by reporting bias, underreporting, duplicate submissions, confounding,
          missing information, and concomitant drugs. PRR, ROR, confidence intervals, and
          prioritization are research aids; they do not establish causality, incidence, clinical
          risk, relative safety, or treatment recommendations.
        </p>
      </section>
    </section>
  )
}

function ComparisonResults({ results }: { results: PairResult[] }) {
  const ready = results.filter(
    (result): result is Extract<PairResult, { status: 'ready' }> => result.status === 'ready',
  )
  return (
    <section className="signal-comparison-results" aria-labelledby="comparison-results-title">
      <div className="results-card__header">
        <div>
          <p className="eyebrow">Selected signals</p>
          <h2 id="comparison-results-title">{results.length} pairs in entered order</h2>
        </div>
        <p className="results-meta">No cross-pair score or ranking</p>
      </div>
      {ready.length === 0 && (
        <EmptyPanel
          title="No selected pairs were observed"
          message="None of these pairs is present in the resolved latest-report population."
        />
      )}
      <div className="signal-comparison-grid">
        {results.map((result, index) => (
          <SignalComparisonCard result={result} index={index} key={`${result.selection.drugName}\u0000${result.selection.reactionTerm}`} />
        ))}
      </div>
      {ready[0] && <p className="inline-notice">{ready[0].response.research_notice}</p>}
    </section>
  )
}

function SignalComparisonCard({ result, index }: { result: PairResult; index: number }) {
  const titleId = `comparison-pair-${index + 1}`
  if (result.status === 'missing') {
    return (
      <article className="signal-comparison-card signal-comparison-card--missing" aria-labelledby={titleId}>
        <p className="eyebrow">Pair {index + 1}</p>
        <h3 id={titleId}>{result.selection.drugName} <span aria-hidden="true">/</span> {result.selection.reactionTerm}</h3>
        <div className="comparison-card-empty">
          <strong>Pair not observed</strong>
          <p>No server-derived signal detail exists in the resolved analytics population.</p>
        </div>
      </article>
    )
  }

  const { signal } = result.response
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
  return (
    <article className="signal-comparison-card" aria-labelledby={titleId}>
      <p className="eyebrow">Pair {index + 1}</p>
      <h3 id={titleId}>{signal.drug_name} <span aria-hidden="true">/</span> {signal.reaction_term}</h3>
      <div className="status-row" aria-label={`Evaluation status for pair ${index + 1}`}>
        <span className={`pill ${signal.is_observed ? 'pill--positive' : ''}`}>
          {signal.is_observed ? 'Observed' : 'Not observed'}
        </span>
        <span className={`pill ${signal.statistically_evaluable ? 'pill--positive' : ''}`}>
          {signal.statistically_evaluable ? 'Evaluable' : 'Not evaluable'}
        </span>
        <span className={`pill ${signal.eligible_for_prioritization ? 'pill--positive' : ''}`}>
          {signal.eligible_for_prioritization ? 'Eligible' : 'Not eligible'}
        </span>
        <span className={`pill ${signal.is_prioritized ? 'pill--accent' : ''}`}>
          {signal.is_prioritized ? 'Prioritized' : 'Not prioritized'}
        </span>
      </div>
      <dl className="signal-comparison-metrics">
        <div><dt>Pair reports</dt><dd>{formatCount(signal.a)}</dd></div>
        <div><dt>Analysis population</dt><dd>{formatCount(signal.analysis_population)}</dd></div>
        <div><dt>PRR</dt><dd>{formatRatio(signal.prr.value)}</dd></div>
        <div><dt>ROR</dt><dd>{formatRatio(signal.ror.value)}</dd></div>
        <div className="signal-comparison-metrics__wide">
          <dt>ROR confidence interval</dt>
          <dd>
            {interval.lower_bound === null || interval.upper_bound === null
              ? 'Not defined'
              : `${formatRatio(interval.lower_bound)}–${formatRatio(interval.upper_bound)}`}
          </dd>
        </div>
      </dl>
      {diagnostics.length > 0 && (
        <div className="comparison-diagnostics">
          <h4>Evaluation notes</h4>
          <ul>{diagnostics.map((reason) => <li key={reason}>{formatReason(reason)}</li>)}</ul>
        </div>
      )}
    </article>
  )
}
