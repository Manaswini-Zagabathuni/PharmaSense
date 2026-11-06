import { useState } from 'react'

interface AnalysisLinkControlProps {
  url: URL | null
}

type CopyState = 'idle' | 'success' | 'error'

export function AnalysisLinkControl({ url }: AnalysisLinkControlProps) {
  const [copyState, setCopyState] = useState<CopyState>('idle')

  async function copyLink() {
    if (url === null) return
    try {
      await navigator.clipboard.writeText(url.href)
      setCopyState('success')
    } catch {
      setCopyState('error')
    }
  }

  return (
    <div className="analysis-link-control">
      <button
        className="button button--secondary"
        type="button"
        onClick={() => void copyLink()}
        disabled={url === null}
        aria-label="Copy analysis link"
      >
        Copy analysis link
      </button>
      <span className="analysis-link-control__feedback" role="status" aria-live="polite">
        {copyState === 'success'
          ? 'Analysis configuration link copied.'
          : copyState === 'error'
            ? 'Unable to copy the analysis link.'
            : url === null
              ? 'Complete a valid configuration to create a link.'
              : 'The link stores configuration, not results.'}
      </span>
      <small>
        Reopening the link reruns the analysis against currently loaded data, so results may change.
      </small>
    </div>
  )
}
