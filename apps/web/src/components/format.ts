export function formatCount(value: number): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value)
}

export function formatRatio(value: number | null): string {
  if (value === null) return 'Not defined'
  return new Intl.NumberFormat('en-US', {
    maximumSignificantDigits: 4,
    minimumSignificantDigits: 2,
  }).format(value)
}

export function formatReason(reason: string): string {
  return reason
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
