import { expect, test } from 'vitest'

import { formatCount, formatRatio, formatReason } from './format'

test('formats API-provided counts, ratios, and diagnostic codes', () => {
  expect(formatCount(12345)).toBe('12,345')
  expect(formatRatio(22.25)).toBe('22.25')
  expect(formatRatio(null)).toBe('Not defined')
  expect(formatReason('BELOW_MINIMUM_PAIR_REPORTS')).toBe('Below Minimum Pair Reports')
})
