import { afterEach, expect, test, vi } from 'vitest'

import {
  ApiError,
  getDrugReactions,
  getDrugs,
  getHistoricalSignal,
  getSignalDetail,
  getSourceSnapshots,
} from './client'

afterEach(() => vi.unstubAllGlobals())

test('builds bounded query and safely encoded path requests', async () => {
  const fetchMock = vi
    .fn()
    .mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 })),
    )
  vi.stubGlobal('fetch', fetchMock)

  await getDrugs(25, 50)
  await getDrugReactions('Drug A/B', 10)
  await getSignalDetail('Drug A/B', 'Event C')
  await getSourceSnapshots(200)
  await getHistoricalSignal({
    drugName: 'Drug A/B',
    reactionTerm: 'Event C/D',
    startQuarter: '2023Q1',
    endQuarter: '2023Q4',
  })

  expect(fetchMock.mock.calls[0]?.[0]).toContain('/drugs?limit=25&offset=50')
  expect(fetchMock.mock.calls[1]?.[0]).toContain('/drugs/Drug%20A%2FB/reactions?limit=10')
  expect(fetchMock.mock.calls[2]?.[0]).toContain('/signals/Drug%20A%2FB/reactions/Event%20C')
  expect(fetchMock.mock.calls[3]?.[0]).toContain('/source-snapshots?limit=200')
  expect(fetchMock.mock.calls[4]?.[0]).toContain(
    '/historical/signals/Drug%20A%2FB/reactions/Event%20C%2FD?start_quarter=2023Q1&end_quarter=2023Q4',
  )
})

test('uses sanitized API and fallback error messages', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Pair not found.' }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(new Response('proxy failure', { status: 502 })),
  )

  await expect(getSignalDetail('Missing', 'Missing')).rejects.toMatchObject({
    message: 'Pair not found.',
    status: 404,
  })
  await expect(getDrugs(1, 0)).rejects.toMatchObject({
    message: 'Request failed with status 502.',
    status: 502,
  })
})

test('distinguishes network failures and preserves abort errors', async () => {
  const abort = new DOMException('aborted', 'AbortError')
  vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new Error('offline')).mockRejectedValueOnce(abort))

  await expect(getDrugs(1, 0)).rejects.toEqual(
    new ApiError('The PharmaSense API could not be reached.'),
  )
  await expect(getDrugs(1, 0)).rejects.toBe(abort)
})
