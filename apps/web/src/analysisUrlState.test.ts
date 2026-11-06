import { afterEach, describe, expect, test } from 'vitest'

import {
  comparisonAnalysisUrl,
  historicalAnalysisUrl,
  parseComparisonUrlState,
  parseHistoricalUrlState,
  workspaceFromSearch,
} from './analysisUrlState'

afterEach(() => window.history.replaceState(null, '', '/'))

describe('historical analysis URLs', () => {
  test('generates and restores a complete encoded configuration across reload parsing', () => {
    const url = historicalAnalysisUrl({
      drugName: 'Drug A/B',
      reactionTerm: 'Head ache',
      startQuarter: '2023Q1',
      endQuarter: '2023Q4',
    })

    expect(url.searchParams.get('workspace')).toBe('historical')
    expect(url.searchParams.get('drug')).toBe('Drug A/B')
    expect(parseHistoricalUrlState(url.search)).toEqual({
      drugName: 'Drug A/B',
      reactionTerm: 'Head ache',
      startQuarter: '2023Q1',
      endQuarter: '2023Q4',
    })
    expect(parseHistoricalUrlState(url.search)).toEqual(parseHistoricalUrlState(url.search))
  })

  test.each([
    '?workspace=historical&drug=A&reaction=B&start=2023-Q1&end=2023Q2',
    '?workspace=historical&drug=A&reaction=B&start=2023Q5&end=2024Q1',
    '?workspace=historical&drug=A&reaction=B&start=2024Q1&end=2023Q4',
    '?workspace=historical&drug=A&start=2023Q1&end=2023Q2',
    '?workspace=historical&drug=A&drug=B&reaction=C&start=2023Q1&end=2023Q2',
  ])('rejects invalid, incomplete, or ambiguous state: %s', (search) => {
    expect(parseHistoricalUrlState(search)).toBeNull()
  })
})

describe('comparison analysis URLs', () => {
  test('generates and restores two to four pairs in entered order', () => {
    const pairs = [
      { drugName: 'First Drug', reactionTerm: 'First Event' },
      { drugName: 'Second Drug', reactionTerm: 'Second Event' },
      { drugName: 'Third Drug', reactionTerm: 'Third Event' },
    ]
    const url = comparisonAnalysisUrl(pairs)

    expect(url.searchParams.getAll('drug')).toEqual(['First Drug', 'Second Drug', 'Third Drug'])
    expect(parseComparisonUrlState(url.search)).toEqual(pairs)
  })

  test.each([
    '?workspace=comparison&drug=A&reaction=X',
    '?workspace=comparison&drug=A&reaction=X&drug=B&reaction=Y&drug=C&reaction=Z&drug=D&reaction=W&drug=E&reaction=V',
    '?workspace=comparison&drug=A&reaction=X&drug=B',
    '?workspace=comparison&drug=A&reaction=X&drug=%20&reaction=Y',
    '?workspace=comparison&drug=A&reaction=X&drug=a&reaction=x',
  ])('rejects out-of-bounds, malformed, incomplete, or duplicate pairs: %s', (search) => {
    expect(parseComparisonUrlState(search)).toBeNull()
  })
})

test('selects only recognized workspaces', () => {
  expect(workspaceFromSearch('?workspace=comparison')).toBe('comparison')
  expect(workspaceFromSearch('?workspace=signals')).toBe('signals')
  expect(workspaceFromSearch('?workspace=unknown')).toBe('overview')
  expect(workspaceFromSearch('')).toBe('overview')
})
