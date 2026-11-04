import { ApiError } from '../api/client'

interface ErrorPanelProps {
  error: unknown
  onRetry: () => void
  title?: string
}

export function LoadingPanel({ label }: { label: string }) {
  return (
    <div className="state-panel" role="status" aria-live="polite">
      <span className="loader" aria-hidden="true" />
      <p>{label}</p>
    </div>
  )
}

export function ErrorPanel({ error, onRetry, title = 'Unable to load analytics' }: ErrorPanelProps) {
  const unavailable = error instanceof ApiError && (error.status === 503 || error.status === null)
  const message = unavailable
    ? 'The analytics service is currently unavailable. Check that the API and database are ready.'
    : error instanceof Error
      ? error.message
      : 'An unexpected request error occurred.'

  return (
    <div className="state-panel state-panel--error" role="alert">
      <p className="state-kicker">{unavailable ? 'Service unavailable' : 'Request failed'}</p>
      <h3>{title}</h3>
      <p>{message}</p>
      <button className="button button--secondary" type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  )
}

export function EmptyPanel({ title, message }: { title: string; message: string }) {
  return (
    <div className="state-panel state-panel--empty">
      <p className="state-kicker">No results</p>
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  )
}
