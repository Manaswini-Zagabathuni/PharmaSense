import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { Signal, SignalDetailResponse } from '../api/types'
import { SignalComparison } from './SignalComparison'

const researchNotice = 'Reporting patterns do not establish causality or incidence.'

const eligibleSignal: Signal = {
  drug_name: 'Drug A',
  reaction_term: 'Event A',
  analysis_population: 1000,
  a: 20,
  b: 80,
  c: 10,
  d: 890,
  prr: { value: 18, undefined_reason: null },
  ror: { value: 22.25, undefined_reason: null },
  ror_confidence_interval: {
    confidence_level: 0.95,
    lower_bound: 10.07,
    upper_bound: 49.16,
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

const unevaluableSignal: Signal = {
  ...eligibleSignal,
  drug_name: 'Drug B',
  reaction_term: 'Event B',
  a: 1,
  b: 0,
  c: 2,
  d: 997,
  prr: { value: 499, undefined_reason: null },
  ror: { value: null, undefined_reason: 'ZERO_DRUG_NON_REACTION_COUNT' },
  ror_confidence_interval: {
    confidence_level: 0.95,
    lower_bound: null,
    upper_bound: null,
    undefined_reason: 'ZERO_CELL_CONFIDENCE_INTERVAL',
  },
  metrics_calculable: false,
  statistically_evaluable: false,
  eligible_for_prioritization: false,
  ineligibility_reasons: [
    'BELOW_MINIMUM_PAIR_REPORTS',
    'ROR_UNDEFINED',
    'ROR_CONFIDENCE_INTERVAL_UNDEFINED',
  ],
  is_prioritized: false,
  priority_exclusion_reason: 'NOT_ELIGIBLE',
}

function detail(signal: Signal): SignalDetailResponse {
  return { signal, research_notice: researchNotice }
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

function fillPair(index: number, drugName: string, reactionTerm: string) {
  fireEvent.change(screen.getByLabelText(`Drug name for pair ${index}`), {
    target: { value: drugName },
  })
  fireEvent.change(screen.getByLabelText(`Reaction term for pair ${index}`), {
    target: { value: reactionTerm },
  })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('validates complete unique selections and bounds the comparison at four pairs', () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  render(<SignalComparison />)

  expect(screen.getByRole('combobox', { name: 'Drug name for pair 1' })).toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: 'Reaction term for pair 1' })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Compare signals' }))
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Enter both a drug name and reaction term for every pair.',
  )

  fillPair(1, 'Drug A', 'Event A')
  fillPair(2, 'drug a', 'event a')
  fireEvent.click(screen.getByRole('button', { name: 'Compare signals' }))
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Each selected drug–reaction pair must be unique.',
  )
  expect(fetchMock).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: 'Add pair' }))
  fireEvent.click(screen.getByRole('button', { name: 'Add pair' }))
  expect(screen.getByText('4 of 4 pairs')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Add pair' })).toBeDisabled()
  expect(screen.getByLabelText('Remove pair 4')).toBeInTheDocument()
  fireEvent.click(screen.getByLabelText('Remove pair 4'))
  expect(screen.getByText('3 of 4 pairs')).toBeInTheDocument()
})

test('compares multiple signals in entered order and preserves server diagnostics', async () => {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = requestUrl(input)
    if (url.includes('/signals/Drug%20A/reactions/Event%20A')) {
      return Promise.resolve(jsonResponse(detail(eligibleSignal)))
    }
    if (url.includes('/signals/Drug%20B/reactions/Event%20B')) {
      return Promise.resolve(jsonResponse(detail(unevaluableSignal)))
    }
    return Promise.reject(new Error(`Unexpected URL: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<SignalComparison />)

  fillPair(1, 'Drug A', 'Event A')
  fillPair(2, 'Drug B', 'Event B')
  fireEvent.click(screen.getByRole('button', { name: 'Compare signals' }))

  expect(screen.getByText('Loading signal comparison…')).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: '2 pairs in entered order' })).toBeInTheDocument()
  const cards = screen.getAllByRole('article')
  expect(cards).toHaveLength(2)
  expect(within(cards[0] as HTMLElement).getByRole('heading', { name: /Drug A.*Event A/ })).toBeInTheDocument()
  expect(within(cards[1] as HTMLElement).getByRole('heading', { name: /Drug B.*Event B/ })).toBeInTheDocument()
  expect(within(cards[0] as HTMLElement).getByText('Prioritized')).toBeInTheDocument()
  expect(within(cards[0] as HTMLElement).getByText('22.25')).toBeInTheDocument()
  expect(within(cards[0] as HTMLElement).getByText('10.07–49.16')).toBeInTheDocument()
  expect(within(cards[1] as HTMLElement).getByText('Not evaluable')).toBeInTheDocument()
  expect(within(cards[1] as HTMLElement).getAllByText('Not defined')).toHaveLength(2)
  expect(within(cards[1] as HTMLElement).getByText('Zero Drug Non Reaction Count')).toBeInTheDocument()
  expect(within(cards[1] as HTMLElement).queryByText(/^0(?:\.0+)?$/)).not.toBeInTheDocument()
  expect(screen.getByText(/No cross-pair score or ranking/)).toBeInTheDocument()
  expect(screen.getByText(/PRR, ROR, confidence intervals, and prioritization are research aids/)).toBeInTheDocument()
})

test('keeps unobserved pairs in deterministic comparison order without fabricated metrics', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input)
      if (url.includes('/signals/Missing/reactions/Unknown')) {
        return Promise.resolve(jsonResponse({ detail: 'not observed' }, 404))
      }
      return Promise.resolve(jsonResponse(detail(eligibleSignal)))
    }),
  )
  render(<SignalComparison />)

  fillPair(1, 'Missing', 'Unknown')
  fillPair(2, 'Drug A', 'Event A')
  fireEvent.click(screen.getByRole('button', { name: 'Compare signals' }))

  const cards = await screen.findAllByRole('article')
  expect(within(cards[0] as HTMLElement).getByText('Pair not observed')).toBeInTheDocument()
  expect(within(cards[0] as HTMLElement).queryByText('0')).not.toBeInTheDocument()
  expect(within(cards[1] as HTMLElement).getByText('22.25')).toBeInTheDocument()
})

test('renders an all-missing empty state', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(jsonResponse({ detail: 'not observed' }, 404)),
  )
  render(<SignalComparison />)

  fillPair(1, 'Missing A', 'Unknown A')
  fillPair(2, 'Missing B', 'Unknown B')
  fireEvent.click(screen.getByRole('button', { name: 'Compare signals' }))

  expect(await screen.findByText('No selected pairs were observed')).toBeInTheDocument()
  expect(screen.getAllByText('Pair not observed')).toHaveLength(2)
})

test('shows API failures and retries the complete bounded comparison', async () => {
  let shouldFail = true
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = requestUrl(input)
    if (shouldFail && url.includes('/signals/Drug%20A/')) {
      shouldFail = false
      return Promise.resolve(jsonResponse({ detail: 'Analytics database is unavailable.' }, 503))
    }
    return Promise.resolve(
      jsonResponse(detail(url.includes('/signals/Drug%20A/') ? eligibleSignal : unevaluableSignal)),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<SignalComparison />)

  fillPair(1, 'Drug A', 'Event A')
  fillPair(2, 'Drug B', 'Event B')
  fireEvent.click(screen.getByRole('button', { name: 'Compare signals' }))

  expect(await screen.findByText('Unable to compare signals')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

  expect(await screen.findByRole('heading', { name: '2 pairs in entered order' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(4)
})
