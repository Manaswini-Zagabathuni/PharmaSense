import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type {
  HistoricalSignalResponse,
  Signal,
  SourceSnapshotListResponse,
} from '../api/types'
import { HistoricalComparison } from './HistoricalComparison'
import { HistoricalTrends } from './HistoricalTrends'

const snapshots: SourceSnapshotListResponse = {
  items: [
    {
      source_quarter: '2023Q1',
      source_name: 'FDA FAERS',
      filename: 'faers_ascii_2023Q1.zip',
      archive_sha256: 'a'.repeat(64),
      retrieved_at: '2026-11-01T00:00:00Z',
      known_in_provenance: true,
      completed_ingestion_runs: 1,
      latest_completed_at: '2026-11-01T01:00:00Z',
      persisted_report_count: 100,
      successfully_loaded_report_count: 100,
      successfully_loaded_case_count: 90,
      contains_successfully_loaded_reports: true,
    },
    {
      source_quarter: '2023Q2',
      source_name: 'FDA FAERS',
      filename: 'faers_ascii_2023Q2.zip',
      archive_sha256: 'b'.repeat(64),
      retrieved_at: '2026-11-02T00:00:00Z',
      known_in_provenance: true,
      completed_ingestion_runs: 1,
      latest_completed_at: '2026-11-02T01:00:00Z',
      persisted_report_count: 120,
      successfully_loaded_report_count: 120,
      successfully_loaded_case_count: 110,
      contains_successfully_loaded_reports: true,
    },
    {
      source_quarter: '2023Q3',
      source_name: 'FDA FAERS',
      filename: 'faers_ascii_2023Q3.zip',
      archive_sha256: 'c'.repeat(64),
      retrieved_at: '2026-11-03T00:00:00Z',
      known_in_provenance: true,
      completed_ingestion_runs: 0,
      latest_completed_at: null,
      persisted_report_count: 5,
      successfully_loaded_report_count: 0,
      successfully_loaded_case_count: 0,
      contains_successfully_loaded_reports: false,
    },
  ],
  returned_count: 3,
  limit: 200,
}

const baseSignal: Signal = {
  drug_name: 'Drug A',
  reaction_term: 'Event B',
  analysis_population: 100,
  a: 20,
  b: 30,
  c: 10,
  d: 40,
  prr: { value: 2, undefined_reason: null },
  ror: { value: 2.6667, undefined_reason: null },
  ror_confidence_interval: {
    confidence_level: 0.95,
    lower_bound: 1.2,
    upper_bound: 5.9,
    undefined_reason: null,
  },
  thresholds: {
    minimum_pair_reports: 3,
    minimum_population: null,
    minimum_ror_lower_bound: 1,
  },
  is_observed: true,
  metrics_calculable: true,
  statistically_evaluable: true,
  eligible_for_prioritization: true,
  ineligibility_reasons: [],
  is_prioritized: true,
  priority_exclusion_reason: null,
}

const historicalResponse: HistoricalSignalResponse = {
  metadata: {
    selection_rule: 'COMPLETED_INGESTIONS_IN_INCLUSIVE_QUARTER_RANGE',
    requested_start_quarter: '2023Q1',
    requested_end_quarter: '2023Q2',
    selected_source_quarters: ['2023Q1', '2023Q2'],
    resolved_report_count: 180,
    resolved_case_count: 180,
    excluded_invalid_version_case_count: 2,
    excluded_version_tie_case_count: 1,
  },
  items: [
    { source_quarter: '2023Q1', signal: baseSignal },
    {
      source_quarter: '2023Q2',
      signal: {
        ...baseSignal,
        analysis_population: 110,
        a: 0,
        b: 20,
        c: 5,
        d: 85,
        prr: { value: 0, undefined_reason: null },
        ror: { value: 0, undefined_reason: null },
        ror_confidence_interval: {
          confidence_level: 0.95,
          lower_bound: null,
          upper_bound: null,
          undefined_reason: 'ZERO_CELL_CONFIDENCE_INTERVAL',
        },
        is_observed: false,
        statistically_evaluable: false,
        eligible_for_prioritization: false,
        ineligibility_reasons: ['PAIR_NOT_OBSERVED', 'BELOW_MINIMUM_PAIR_REPORTS'],
        is_prioritized: false,
        priority_exclusion_reason: 'NOT_ELIGIBLE',
      },
    },
  ],
  returned_count: 2,
  research_notice: 'Reporting patterns do not establish causality or incidence.',
  historical_method_notice:
    'Results filter loaded completed source quarters and are not a retrospective as-of reconstruction.',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return input.url
}

function fillHistoricalForm() {
  fireEvent.change(screen.getByLabelText('Drug name'), { target: { value: 'Drug A' } })
  fireEvent.change(screen.getByLabelText('Reaction term'), { target: { value: 'Event B' } })
  fireEvent.click(screen.getByRole('button', { name: 'Analyze history' }))
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('renders API-provided quarter results, diagnostics, and source provenance', async () => {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = requestUrl(input)
    if (url.includes('/source-snapshots?')) return Promise.resolve(jsonResponse(snapshots))
    if (url.includes('/historical/signals/')) {
      return Promise.resolve(jsonResponse(historicalResponse))
    }
    return Promise.reject(new Error(`Unexpected URL: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<HistoricalTrends />)

  expect(screen.getByText('Loading source-quarter inventory…')).toBeInTheDocument()
  expect(await screen.findByText('Choose a drug–reaction pair')).toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: 'Drug name' })).toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: 'Reaction term' })).toBeInTheDocument()
  expect(screen.getByLabelText('Start quarter')).toHaveValue('2023Q1')
  expect(screen.getByLabelText('End quarter')).toHaveValue('2023Q2')

  fillHistoricalForm()

  const resultHeading = await screen.findByRole('heading', { name: '2 loaded quarters' })
  const comparison = screen.getByRole('region', { name: 'Historical Comparison' })
  expect(within(comparison).getByRole('radio', { name: 'ROR' })).toBeChecked()
  expect(within(comparison).getByRole('list', { name: 'ROR by source quarter' })).toBeInTheDocument()
  expect(within(comparison).getByText('2.667')).toBeInTheDocument()
  expect(within(comparison).getByText('0.0')).toBeInTheDocument()
  fireEvent.click(within(comparison).getByRole('radio', { name: 'ROR confidence interval' }))
  expect(within(comparison).getByText('1.2–5.9')).toBeInTheDocument()
  expect(within(comparison).getByText('Zero Cell Confidence Interval')).toBeInTheDocument()
  fireEvent.click(within(comparison).getByRole('radio', { name: 'Pair reports' }))
  expect(within(comparison).getByText('20')).toBeInTheDocument()
  expect(within(comparison).getByText('0')).toBeInTheDocument()
  fireEvent.click(within(comparison).getByRole('radio', { name: 'PRR' }))
  expect(within(comparison).getByText('2.0')).toBeInTheDocument()
  expect(within(comparison).getByText('0.0')).toBeInTheDocument()
  const results = resultHeading.closest('.results-card')
  expect(results).not.toBeNull()
  expect(within(results as HTMLElement).getByText('2.667')).toBeInTheDocument()
  expect(within(results as HTMLElement).getByText('1.2–5.9')).toBeInTheDocument()
  expect(within(results as HTMLElement).getByText('Pair Not Observed')).toBeInTheDocument()
  expect(within(results as HTMLElement).getByText('Not defined')).toBeInTheDocument()
  expect(screen.getByText(/PRR and ROR do not establish causality/)).toBeInTheDocument()

  fireEvent.click(screen.getByText('Source snapshots and reproducibility'))
  expect(screen.getByText('faers_ascii_2023Q1.zip')).toBeInTheDocument()
  expect(screen.getByText('faers_ascii_2023Q3.zip')).toBeInTheDocument()
  expect(screen.getByText('Provenance only or incomplete')).toBeInTheDocument()
  expect(screen.getByText(/not a retrospective as-of reconstruction/)).toBeInTheDocument()
  expect(fetchMock.mock.calls[1]?.[0]).toContain(
    '/historical/signals/Drug%20A/reactions/Event%20B?start_quarter=2023Q1&end_quarter=2023Q2',
  )
})

test('orders requested quarters and distinguishes missing, undefined, and zero API values', () => {
  const response: HistoricalSignalResponse = {
    ...historicalResponse,
    metadata: {
      ...historicalResponse.metadata,
      requested_start_quarter: '2023Q1',
      requested_end_quarter: '2023Q3',
      selected_source_quarters: ['2023Q1', '2023Q3'],
    },
    items: [
      {
        source_quarter: '2023Q3',
        signal: {
          ...baseSignal,
          ror: { value: null, undefined_reason: 'ZERO_NON_DRUG_REACTION_COUNT' },
          statistically_evaluable: false,
          eligible_for_prioritization: false,
          is_prioritized: false,
          ineligibility_reasons: ['ROR_UNDEFINED'],
          priority_exclusion_reason: 'NOT_ELIGIBLE',
        },
      },
      { source_quarter: '2023Q1', signal: baseSignal },
    ],
    returned_count: 2,
  }

  render(<HistoricalComparison response={response} />)

  const comparison = screen.getByRole('region', { name: 'Historical Comparison' })
  const rows = within(comparison).getAllByRole('listitem')
  expect(rows).toHaveLength(3)
  expect(rows[0]).toHaveTextContent('2023Q1')
  expect(rows[1]).toHaveTextContent('2023Q2')
  expect(rows[1]).toHaveTextContent('No loaded result')
  expect(rows[2]).toHaveTextContent('2023Q3')
  expect(rows[2]).toHaveTextContent('Not defined')
  expect(rows[2]).toHaveTextContent('Zero Non Drug Reaction Count')
  expect(within(rows[2] as HTMLElement).queryByText(/^0(?:\.0+)?$/)).not.toBeInTheDocument()

  fireEvent.click(within(comparison).getByRole('radio', { name: 'Pair reports' }))
  expect(within(comparison).getByRole('list', { name: 'Pair reports by source quarter' })).toBeInTheDocument()
  expect(rows[1]).toHaveTextContent('No loaded result')
})

test('shows validation and a historical loading state without fabricating results', async () => {
  let resolveHistorical: ((response: Response) => void) | undefined
  const pendingHistorical = new Promise<Response>((resolve) => {
    resolveHistorical = resolve
  })
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input)
      return url.includes('/source-snapshots?')
        ? Promise.resolve(jsonResponse(snapshots))
        : pendingHistorical
    }),
  )

  render(<HistoricalTrends />)
  await screen.findByText('Choose a drug–reaction pair')
  fireEvent.click(screen.getByRole('button', { name: 'Analyze history' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Enter both a drug name and a reaction term.')

  fillHistoricalForm()
  expect(screen.getByText('Loading historical reporting measurements…')).toBeInTheDocument()
  expect(screen.queryByText('2 loaded quarters')).not.toBeInTheDocument()

  resolveHistorical?.(jsonResponse(historicalResponse))
  expect(await screen.findByText('2 loaded quarters')).toBeInTheDocument()
})

test('renders an empty historical result and preserves reproducibility metadata', async () => {
  const emptyResponse: HistoricalSignalResponse = {
    ...historicalResponse,
    items: [],
    returned_count: 0,
    metadata: {
      ...historicalResponse.metadata,
      selected_source_quarters: [],
      resolved_report_count: 0,
      resolved_case_count: 0,
    },
  }
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) =>
      Promise.resolve(
        jsonResponse(requestUrl(input).includes('/source-snapshots?') ? snapshots : emptyResponse),
      ),
    ),
  )

  render(<HistoricalTrends />)
  await screen.findByText('Choose a drug–reaction pair')
  fillHistoricalForm()

  expect(await screen.findByText('No loaded quarters matched this range')).toBeInTheDocument()
  fireEvent.click(screen.getByText('Source snapshots and reproducibility'))
  expect(screen.getByText('None')).toBeInTheDocument()
})

test('shows a sanitized API error and retries the historical request', async () => {
  let historicalCalls = 0
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input)
      if (url.includes('/source-snapshots?')) return Promise.resolve(jsonResponse(snapshots))
      historicalCalls += 1
      if (historicalCalls === 1) {
        return Promise.resolve(jsonResponse({ detail: 'Analytics database is unavailable.' }, 503))
      }
      return Promise.resolve(jsonResponse(historicalResponse))
    }),
  )

  render(<HistoricalTrends />)
  await screen.findByText('Choose a drug–reaction pair')
  fillHistoricalForm()

  expect(await screen.findByText('Unable to load historical results')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

  expect(await screen.findByText('2 loaded quarters')).toBeInTheDocument()
  expect(historicalCalls).toBe(2)
})

test('retries source inventory failures and exposes only completed quarters as options', async () => {
  let snapshotCalls = 0
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(() => {
      snapshotCalls += 1
      if (snapshotCalls === 1) return Promise.reject(new Error('offline'))
      return Promise.resolve(jsonResponse(snapshots))
    }),
  )

  render(<HistoricalTrends />)

  expect(await screen.findByText('Unable to load source quarters')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

  const start = await screen.findByLabelText('Start quarter')
  expect(within(start).queryByRole('option', { name: '2023Q3' })).not.toBeInTheDocument()
  await waitFor(() => expect(snapshotCalls).toBe(2))
})
