import { useMemo, useState } from 'react'

import type { HistoricalSignalResponse, QuarterSignal, UndefinedMetricReason } from '../api/types'
import { formatCount, formatRatio, formatReason } from './format'

type ComparisonMetric = 'ror' | 'prr' | 'pairReports' | 'rorInterval'

const METRICS: { value: ComparisonMetric; label: string }[] = [
  { value: 'ror', label: 'ROR' },
  { value: 'prr', label: 'PRR' },
  { value: 'pairReports', label: 'Pair reports' },
  { value: 'rorInterval', label: 'ROR confidence interval' },
]

interface ComparisonRow {
  quarter: string
  item: QuarterSignal | null
}

export function HistoricalComparison({ response }: { response: HistoricalSignalResponse }) {
  const [metric, setMetric] = useState<ComparisonMetric>('ror')
  const rows = useMemo(() => comparisonRows(response), [response])
  const domainMaximum = useMemo(() => maximumDisplayValue(rows, metric), [rows, metric])
  const metricLabel = METRICS.find((option) => option.value === metric)?.label ?? 'Metric'

  return (
    <section
      className="comparison-card"
      aria-labelledby="historical-comparison-title"
      aria-describedby="historical-comparison-description"
    >
      <div className="comparison-card__header">
        <div>
          <p className="eyebrow">Visual comparison</p>
          <h2 id="historical-comparison-title">Historical Comparison</h2>
          <p id="historical-comparison-description">
            Values and intervals come directly from the API. Bar and interval lengths are scaled
            only to the largest available value currently displayed.
          </p>
        </div>
        <fieldset className="metric-selector">
          <legend>Comparison metric</legend>
          {METRICS.map((option) => (
            <label key={option.value}>
              <input
                type="radio"
                name="historical-comparison-metric"
                value={option.value}
                checked={metric === option.value}
                onChange={() => setMetric(option.value)}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </fieldset>
      </div>

      <ol className="comparison-list" aria-label={`${metricLabel} by source quarter`}>
        {rows.map((row) => (
          <ComparisonRowView
            row={row}
            metric={metric}
            domainMaximum={domainMaximum}
            key={row.quarter}
          />
        ))}
      </ol>
      <div className="comparison-legend" aria-label="Comparison status legend">
        <span><i className="legend-mark legend-mark--available" aria-hidden="true" />API value available</span>
        <span><i className="legend-mark legend-mark--undefined" aria-hidden="true" />Undefined or unevaluable</span>
        <span><i className="legend-mark legend-mark--missing" aria-hidden="true" />No loaded result</span>
      </div>
    </section>
  )
}

function ComparisonRowView({
  row,
  metric,
  domainMaximum,
}: {
  row: ComparisonRow
  metric: ComparisonMetric
  domainMaximum: number
}) {
  if (row.item === null) {
    return (
      <li className="comparison-row comparison-row--missing">
        <strong className="comparison-quarter">{row.quarter}</strong>
        <div className="comparison-missing">No loaded result</div>
        <span className="pill">Missing quarter</span>
      </li>
    )
  }

  const { signal } = row.item
  const status = signal.is_prioritized
    ? 'Prioritized'
    : signal.statistically_evaluable
      ? 'Evaluable'
      : 'Not evaluable'

  if (metric === 'rorInterval') {
    const interval = signal.ror_confidence_interval
    const lower = interval.lower_bound
    const upper = interval.upper_bound
    const defined = lower !== null && upper !== null
    return (
      <li className={`comparison-row ${defined ? '' : 'comparison-row--undefined'}`}>
        <strong className="comparison-quarter">{row.quarter}</strong>
        {lower !== null && upper !== null ? (
          <div className="comparison-value-group">
            <IntervalMark
              lower={lower}
              upper={upper}
              point={signal.ror.value}
              domainMaximum={domainMaximum}
            />
            <span className="comparison-value">
              {formatRatio(lower)}–{formatRatio(upper)}
            </span>
          </div>
        ) : (
          <UndefinedValue reason={interval.undefined_reason} />
        )}
        <span className={`pill ${signal.is_prioritized ? 'pill--accent' : ''}`}>{status}</span>
      </li>
    )
  }

  const value = metricValue(row.item, metric)
  const reason = metricUndefinedReason(row.item, metric)
  return (
    <li className={`comparison-row ${value === null ? 'comparison-row--undefined' : ''}`}>
      <strong className="comparison-quarter">{row.quarter}</strong>
      {value === null ? (
        <UndefinedValue reason={reason} />
      ) : (
        <div className="comparison-value-group">
          <div className="bar-track" aria-hidden="true">
            <span className="bar-fill" style={{ width: `${displayPercent(value, domainMaximum)}%` }} />
          </div>
          <span className="comparison-value">
            {metric === 'pairReports' ? formatCount(value) : formatRatio(value)}
          </span>
        </div>
      )}
      <span className={`pill ${signal.is_prioritized ? 'pill--accent' : ''}`}>{status}</span>
    </li>
  )
}

function IntervalMark({
  lower,
  upper,
  point,
  domainMaximum,
}: {
  lower: number
  upper: number
  point: number | null
  domainMaximum: number
}) {
  const lowerPosition = displayPercent(lower, domainMaximum)
  const upperPosition = displayPercent(upper, domainMaximum)
  const pointPosition = point === null ? null : displayPercent(point, domainMaximum)
  return (
    <div className="interval-track" aria-hidden="true">
      <span
        className="interval-range"
        style={{ left: `${lowerPosition}%`, width: `${upperPosition - lowerPosition}%` }}
      />
      {pointPosition !== null && <span className="interval-point" style={{ left: `${pointPosition}%` }} />}
    </div>
  )
}

function UndefinedValue({ reason }: { reason: UndefinedMetricReason | null }) {
  return (
    <div className="comparison-undefined">
      <strong>Not defined</strong>
      <small>{reason === null ? 'No API estimate available' : formatReason(reason)}</small>
    </div>
  )
}

function comparisonRows(response: HistoricalSignalResponse): ComparisonRow[] {
  const byQuarter = new Map(response.items.map((item) => [item.source_quarter, item]))
  return inclusiveQuarters(
    response.metadata.requested_start_quarter,
    response.metadata.requested_end_quarter,
  ).map((quarter) => ({ quarter, item: byQuarter.get(quarter) ?? null }))
}

function inclusiveQuarters(start: string, end: string): string[] {
  const startYear = Number(start.slice(0, 4))
  const startQuarter = Number(start.slice(5))
  const endYear = Number(end.slice(0, 4))
  const endQuarter = Number(end.slice(5))
  const startOrdinal = startYear * 4 + startQuarter - 1
  const endOrdinal = endYear * 4 + endQuarter - 1
  const quarters: string[] = []
  for (let ordinal = startOrdinal; ordinal <= endOrdinal && quarters.length < 80; ordinal += 1) {
    const year = Math.floor(ordinal / 4)
    const quarter = (ordinal % 4) + 1
    quarters.push(`${String(year).padStart(4, '0')}Q${String(quarter)}`)
  }
  return quarters
}

function metricValue(item: QuarterSignal, metric: Exclude<ComparisonMetric, 'rorInterval'>) {
  if (metric === 'pairReports') return item.signal.a
  return metric === 'ror' ? item.signal.ror.value : item.signal.prr.value
}

function metricUndefinedReason(
  item: QuarterSignal,
  metric: Exclude<ComparisonMetric, 'rorInterval'>,
): UndefinedMetricReason | null {
  if (metric === 'pairReports') return null
  return metric === 'ror'
    ? item.signal.ror.undefined_reason
    : item.signal.prr.undefined_reason
}

function maximumDisplayValue(rows: ComparisonRow[], metric: ComparisonMetric): number {
  const values = rows.flatMap((row) => {
    if (row.item === null) return []
    if (metric === 'rorInterval') {
      const interval = row.item.signal.ror_confidence_interval
      return interval.upper_bound === null ? [] : [interval.upper_bound]
    }
    const value = metricValue(row.item, metric)
    return value === null ? [] : [value]
  })
  return Math.max(0, ...values)
}

function displayPercent(value: number, domainMaximum: number): number {
  if (domainMaximum === 0) return 0
  return Math.min(100, Math.max(0, (value / domainMaximum) * 100))
}
