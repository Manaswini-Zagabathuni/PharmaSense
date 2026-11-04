import type {
  DrugListResponse,
  DrugReactionListResponse,
  ErrorResponse,
  SignalDetailResponse,
  SignalListResponse,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export class ApiError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as Partial<ErrorResponse>
    if (typeof body.detail === 'string' && body.detail.length > 0) return body.detail
  } catch {
    // The API may be unavailable or return a non-JSON proxy response.
  }
  return `Request failed with status ${String(response.status)}.`
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('The PharmaSense API could not be reached.')
  }
  if (!response.ok) throw new ApiError(await parseError(response), response.status)
  return (await response.json()) as T
}

export interface SignalQuery {
  limit: number
  minimumPairReports: number
  minimumRorLowerBound: number
}

export function getSignals(query: SignalQuery, signal?: AbortSignal): Promise<SignalListResponse> {
  const params = new URLSearchParams({
    limit: String(query.limit),
    minimum_pair_reports: String(query.minimumPairReports),
    minimum_ror_lower_bound: String(query.minimumRorLowerBound),
  })
  return request<SignalListResponse>(`/signals?${params.toString()}`, signal)
}

export function getSignalDetail(
  drugName: string,
  reactionTerm: string,
  signal?: AbortSignal,
): Promise<SignalDetailResponse> {
  const drug = encodeURIComponent(drugName)
  const reaction = encodeURIComponent(reactionTerm)
  return request<SignalDetailResponse>(`/signals/${drug}/reactions/${reaction}`, signal)
}

export function getDrugs(
  limit: number,
  offset: number,
  signal?: AbortSignal,
): Promise<DrugListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  return request<DrugListResponse>(`/drugs?${params.toString()}`, signal)
}

export function getDrugReactions(
  drugName: string,
  limit: number,
  signal?: AbortSignal,
): Promise<DrugReactionListResponse> {
  const params = new URLSearchParams({ limit: String(limit) })
  return request<DrugReactionListResponse>(
    `/drugs/${encodeURIComponent(drugName)}/reactions?${params.toString()}`,
    signal,
  )
}
