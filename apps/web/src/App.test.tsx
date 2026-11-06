import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { Signal } from './api/types'
import { App } from './App'

const researchNotice = 'Reporting patterns do not establish causality or incidence.'

const signal: Signal = {
  drug_name: 'Drug A',
  reaction_term: 'Head ache',
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

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('renders prioritized signals and loads an encoded signal detail', async () => {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = requestUrl(input)
    if (url.includes('/signals/Drug%20A/reactions/Head%20ache')) {
      return Promise.resolve(jsonResponse({ signal, research_notice: researchNotice }))
    }
    if (url.includes('/signals?')) {
      return Promise.resolve(
        jsonResponse({ items: [signal], returned_count: 1, limit: 25, research_notice: researchNotice }),
      )
    }
    return Promise.reject(new Error(`Unexpected URL: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)

  expect(screen.getByRole('heading', { name: 'Signal Explorer' })).toBeInTheDocument()
  expect(await screen.findByText('Drug A')).toBeInTheDocument()
  expect(screen.getByText('22.25')).toBeInTheDocument()
  expect(screen.getByText('10.07–49.16')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Inspect' }))

  expect(await screen.findByRole('heading', { name: /Drug A.*Head ache/ })).toBeInTheDocument()
  expect(screen.getByText('Contingency counts')).toBeInTheDocument()
  expect(screen.getByText('Statistically evaluable')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/signals/Drug%20A/reactions/Head%20ache'),
    expect.objectContaining({ headers: { Accept: 'application/json' } }),
  )
})

test('shows an unavailable state and can retry the signal request', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse({ detail: 'Analytics database is unavailable.' }, 503))
    .mockResolvedValueOnce(
      jsonResponse({ items: [signal], returned_count: 1, limit: 25, research_notice: researchNotice }),
    )
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)

  expect(await screen.findByText('Service unavailable')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

  expect(await screen.findByText('Drug A')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

test('renders a clear empty signal state and applies API-supported filters', async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    jsonResponse({ items: [], returned_count: 0, limit: 10, research_notice: researchNotice }),
  )
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)

  expect(await screen.findByText('No prioritized signals meet these thresholds')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Results'), { target: { value: '10' } })
  fireEvent.change(screen.getByLabelText('Minimum pair reports'), { target: { value: '5' } })
  fireEvent.change(screen.getByLabelText('Minimum ROR lower bound'), { target: { value: '2' } })
  fireEvent.click(screen.getByRole('button', { name: 'Apply filters' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls[1]?.[0]).toContain('limit=10')
  expect(fetchMock.mock.calls[1]?.[0]).toContain('minimum_pair_reports=5')
  expect(fetchMock.mock.calls[1]?.[0]).toContain('minimum_ror_lower_bound=2')
})

test('renders drug summaries and a co-reported reaction profile', async () => {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = requestUrl(input)
    if (url.includes('/drugs/Drug%20A/reactions')) {
      return Promise.resolve(
        jsonResponse({
          drug_name: 'Drug A',
          items: [{ drug_name: 'Drug A', reaction_term: 'Head ache', report_count: 20, case_count: 20 }],
          returned_count: 1,
          limit: 25,
          research_notice: researchNotice,
        }),
      )
    }
    if (url.includes('/drugs?')) {
      return Promise.resolve(
        jsonResponse({
          items: [{ drug_name: 'Drug A', report_count: 30, case_count: 30 }],
          returned_count: 1,
          limit: 25,
          offset: 0,
          research_notice: researchNotice,
        }),
      )
    }
    if (url.includes('/signals?')) {
      return Promise.resolve(jsonResponse({ items: [], returned_count: 0, limit: 25, research_notice: researchNotice }))
    }
    return Promise.reject(new Error(`Unexpected URL: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Drugs' }))

  expect(await screen.findByRole('heading', { name: 'Drug Explorer' })).toBeInTheDocument()
  expect(await screen.findAllByText('30')).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: 'View reactions' }))

  expect(await screen.findByText('Head ache')).toBeInTheDocument()
  expect(screen.getByText(/Co-reporting does not establish causality/i)).toBeInTheDocument()
  expect(screen.getByText('20 reports · 20 cases')).toBeInTheDocument()
})

test('handles a missing drug reaction profile without a live backend', async () => {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = requestUrl(input)
    if (url.includes('/drugs/Missing/reactions')) {
      return Promise.resolve(jsonResponse({ detail: 'Drug was not found.' }, 404))
    }
    if (url.includes('/drugs?')) {
      return Promise.resolve(
        jsonResponse({
          items: [{ drug_name: 'Missing', report_count: 1, case_count: 1 }],
          returned_count: 1,
          limit: 25,
          offset: 0,
          research_notice: researchNotice,
        }),
      )
    }
    return Promise.resolve(jsonResponse({ items: [], returned_count: 0, limit: 25, research_notice: researchNotice }))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Drugs' }))
  fireEvent.click(await screen.findByRole('button', { name: 'View reactions' }))

  expect(await screen.findByText('Drug not found')).toBeInTheDocument()
})

test('renders signal diagnostics, undefined metrics, and close behavior', async () => {
  const diagnostic: Signal = {
    ...signal,
    prr: { value: null, undefined_reason: 'ZERO_COMPARATOR_REACTION_COUNT' },
    ror: { value: null, undefined_reason: 'ZERO_NON_DRUG_REACTION_COUNT' },
    ror_confidence_interval: {
      confidence_level: 0.95,
      lower_bound: null,
      upper_bound: null,
      undefined_reason: 'ZERO_CELL_CONFIDENCE_INTERVAL',
    },
    statistically_evaluable: false,
    eligible_for_prioritization: false,
    ineligibility_reasons: ['PRR_UNDEFINED', 'ROR_UNDEFINED'],
    is_prioritized: false,
    priority_exclusion_reason: 'NOT_ELIGIBLE',
  }
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input)
      return Promise.resolve(
        url.includes('/signals/Drug%20A/')
          ? jsonResponse({ signal: diagnostic, research_notice: researchNotice })
          : jsonResponse({ items: [signal], returned_count: 1, limit: 25, research_notice: researchNotice }),
      )
    }),
  )

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'Inspect' }))

  expect(await screen.findByText('Not evaluable')).toBeInTheDocument()
  expect(screen.getByText('Not prioritized')).toBeInTheDocument()
  expect(screen.getAllByText('Not defined').length).toBeGreaterThan(1)
  expect(screen.getByText('Prr Undefined')).toBeInTheDocument()
  expect(screen.getByText('Not Eligible')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Close detail' }))
  expect(screen.queryByText('Contingency counts')).not.toBeInTheDocument()
})

test('handles missing signal details and failed detail requests', async () => {
  let detailCalls = 0
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input)
      if (url.includes('/signals/Drug%20A/')) {
        detailCalls += 1
        if (detailCalls === 1) return Promise.resolve(jsonResponse({ detail: 'missing' }, 404))
      }
      return Promise.resolve(
        jsonResponse({ items: [signal], returned_count: 1, limit: 25, research_notice: researchNotice }),
      )
    }),
  )

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'Inspect' }))

  expect(await screen.findByText('Pair not observed')).toBeInTheDocument()
})

test('renders empty drug and known-drug empty-reaction states', async () => {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = requestUrl(input)
    if (url.includes('/drugs/Known/reactions')) {
      return Promise.resolve(
        jsonResponse({ drug_name: 'Known', items: [], returned_count: 0, limit: 25, research_notice: researchNotice }),
      )
    }
    if (url.includes('/drugs?')) {
      return Promise.resolve(
        jsonResponse({
          items: [{ drug_name: 'Known', report_count: 1, case_count: 1 }],
          returned_count: 1,
          limit: 25,
          offset: 0,
          research_notice: researchNotice,
        }),
      )
    }
    return Promise.resolve(jsonResponse({ items: [], returned_count: 0, limit: 25, research_notice: researchNotice }))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Drugs' }))
  fireEvent.click(await screen.findByRole('button', { name: 'View reactions' }))

  expect(await screen.findByText('No reactions reported')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Close reactions' }))
  expect(screen.queryByText('No reactions reported')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Signals' }))
  expect(screen.getByRole('heading', { name: 'Signal Explorer' })).toBeInTheDocument()
})

test('supports bounded drug pagination and returning from an empty trailing page', async () => {
  const firstPage = Array.from({ length: 25 }, (_, index) => ({
    drug_name: `Drug ${String(index + 1)}`,
    report_count: 100 - index,
    case_count: 100 - index,
  }))
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = requestUrl(input)
    if (url.includes('/drugs?')) {
      const trailing = url.includes('offset=25')
      return Promise.resolve(
        jsonResponse({
          items: trailing ? [] : firstPage,
          returned_count: trailing ? 0 : 25,
          limit: 25,
          offset: trailing ? 25 : 0,
          research_notice: researchNotice,
        }),
      )
    }
    return Promise.resolve(jsonResponse({ items: [], returned_count: 0, limit: 25, research_notice: researchNotice }))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Drugs' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Next' }))

  expect(await screen.findByText('No more drugs on this page')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Previous page' }))
  expect(await screen.findByText('Drug 1')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some((call) => String(call[0]).includes('offset=25'))).toBe(true)
})

test('retries a failed signal detail request', async () => {
  let detailCalls = 0
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input)
      if (url.includes('/signals/Drug%20A/')) {
        detailCalls += 1
        if (detailCalls === 1) return Promise.reject(new Error('offline'))
        return Promise.resolve(jsonResponse({ signal, research_notice: researchNotice }))
      }
      return Promise.resolve(
        jsonResponse({ items: [signal], returned_count: 1, limit: 25, research_notice: researchNotice }),
      )
    }),
  )

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'Inspect' }))
  expect(await screen.findByText('Service unavailable')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

  expect(await screen.findByText('Contingency counts')).toBeInTheDocument()
  expect(detailCalls).toBe(2)
})

test('retries failed drug and reaction requests', async () => {
  let drugCalls = 0
  let reactionCalls = 0
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input)
      if (url.includes('/drugs/Retry%20Drug/reactions')) {
        reactionCalls += 1
        if (reactionCalls === 1) return Promise.reject(new Error('reaction offline'))
        return Promise.resolve(
          jsonResponse({
            drug_name: 'Retry Drug',
            items: [{ drug_name: 'Retry Drug', reaction_term: 'Recovered Event', report_count: 2, case_count: 2 }],
            returned_count: 1,
            limit: 25,
            research_notice: researchNotice,
          }),
        )
      }
      if (url.includes('/drugs?')) {
        drugCalls += 1
        if (drugCalls === 1) return Promise.reject(new Error('drug offline'))
        return Promise.resolve(
          jsonResponse({
            items: [{ drug_name: 'Retry Drug', report_count: 2, case_count: 2 }],
            returned_count: 1,
            limit: 25,
            offset: 0,
            research_notice: researchNotice,
          }),
        )
      }
      return Promise.resolve(jsonResponse({ items: [], returned_count: 0, limit: 25, research_notice: researchNotice }))
    }),
  )

  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Drugs' }))
  expect(await screen.findByText('Service unavailable')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  fireEvent.click(await screen.findByRole('button', { name: 'View reactions' }))
  expect(await screen.findByText('Service unavailable')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

  expect(await screen.findByText('Recovered Event')).toBeInTheDocument()
  expect(drugCalls).toBe(2)
  expect(reactionCalls).toBe(2)
})

test('opens the Historical Trends workspace without changing existing navigation', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input)
      if (url.includes('/source-snapshots?')) {
        return Promise.resolve(jsonResponse({ items: [], returned_count: 0, limit: 200 }))
      }
      return Promise.resolve(
        jsonResponse({ items: [], returned_count: 0, limit: 25, research_notice: researchNotice }),
      )
    }),
  )

  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Historical Trends' }))

  expect(screen.getByRole('heading', { name: 'Historical Trends' })).toBeInTheDocument()
  expect(await screen.findByText('No completed source quarters are available')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Signals' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Drugs' })).toBeInTheDocument()
})
