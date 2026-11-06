export type AnalysisWorkspace = 'overview' | 'signals' | 'drugs' | 'historical' | 'comparison'

export interface HistoricalUrlState {
  drugName: string
  reactionTerm: string
  startQuarter: string
  endQuarter: string
}

export interface ComparisonUrlPair {
  drugName: string
  reactionTerm: string
}

const MAXIMUM_TERM_LENGTH = 1000
const MINIMUM_COMPARISON_PAIRS = 2
const MAXIMUM_COMPARISON_PAIRS = 4
const QUARTER_PATTERN = /^\d{4}Q[1-4]$/

function exactlyOne(params: URLSearchParams, name: string): string | null {
  const values = params.getAll(name)
  return values.length === 1 ? values[0] ?? null : null
}

export function isValidAnalysisTerm(value: string | null): value is string {
  return value !== null && value.trim().length > 0 && value.trim().length <= MAXIMUM_TERM_LENGTH
}

export function workspaceFromSearch(search: string): AnalysisWorkspace {
  const workspace = new URLSearchParams(search).get('workspace')
  if (
    workspace === 'signals' ||
    workspace === 'drugs' ||
    workspace === 'historical' ||
    workspace === 'comparison'
  ) {
    return workspace
  }
  return 'overview'
}

export function hasHistoricalUrlParameters(search: string): boolean {
  const params = new URLSearchParams(search)
  return ['drug', 'reaction', 'start', 'end'].some((name) => params.has(name))
}

export function parseHistoricalUrlState(search: string): HistoricalUrlState | null {
  const params = new URLSearchParams(search)
  if (params.get('workspace') !== 'historical') return null

  const drugName = exactlyOne(params, 'drug')
  const reactionTerm = exactlyOne(params, 'reaction')
  const startQuarter = exactlyOne(params, 'start')
  const endQuarter = exactlyOne(params, 'end')
  if (
    !isValidAnalysisTerm(drugName) ||
    !isValidAnalysisTerm(reactionTerm) ||
    startQuarter === null ||
    endQuarter === null ||
    !QUARTER_PATTERN.test(startQuarter) ||
    !QUARTER_PATTERN.test(endQuarter) ||
    startQuarter > endQuarter
  ) {
    return null
  }
  return {
    drugName: drugName.trim(),
    reactionTerm: reactionTerm.trim(),
    startQuarter,
    endQuarter,
  }
}

export function hasComparisonUrlParameters(search: string): boolean {
  const params = new URLSearchParams(search)
  return params.has('drug') || params.has('reaction')
}

export function parseComparisonUrlState(search: string): ComparisonUrlPair[] | null {
  const params = new URLSearchParams(search)
  if (params.get('workspace') !== 'comparison') return null
  const drugs = params.getAll('drug')
  const reactions = params.getAll('reaction')
  if (
    drugs.length !== reactions.length ||
    drugs.length < MINIMUM_COMPARISON_PAIRS ||
    drugs.length > MAXIMUM_COMPARISON_PAIRS
  ) {
    return null
  }

  const pairs: ComparisonUrlPair[] = []
  const identities = new Set<string>()
  for (const [index, drug] of drugs.entries()) {
    const reaction = reactions[index] ?? null
    if (!isValidAnalysisTerm(drug) || !isValidAnalysisTerm(reaction)) return null
    const pair = { drugName: drug.trim(), reactionTerm: reaction.trim() }
    const identity = `${pair.drugName.toLowerCase()}\u0000${pair.reactionTerm.toLowerCase()}`
    if (identities.has(identity)) return null
    identities.add(identity)
    pairs.push(pair)
  }
  return pairs
}

function baseAnalysisUrl(workspace: AnalysisWorkspace): URL {
  const url = new URL(window.location.href)
  url.search = ''
  url.hash = ''
  if (workspace !== 'overview') url.searchParams.set('workspace', workspace)
  return url
}

export function workspaceUrl(workspace: AnalysisWorkspace): URL {
  return baseAnalysisUrl(workspace)
}

export function historicalAnalysisUrl(state: HistoricalUrlState): URL {
  const url = baseAnalysisUrl('historical')
  url.searchParams.set('drug', state.drugName)
  url.searchParams.set('reaction', state.reactionTerm)
  url.searchParams.set('start', state.startQuarter)
  url.searchParams.set('end', state.endQuarter)
  return url
}

export function comparisonAnalysisUrl(pairs: ComparisonUrlPair[]): URL {
  const url = baseAnalysisUrl('comparison')
  for (const pair of pairs) {
    url.searchParams.append('drug', pair.drugName)
    url.searchParams.append('reaction', pair.reactionTerm)
  }
  return url
}

export function replaceBrowserUrl(url: URL): void {
  window.history.replaceState(null, '', url)
}
