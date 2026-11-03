import { useEffect, useState } from 'react'

type ApiState = 'checking' | 'available' | 'unavailable'

interface HealthResponse {
  status: 'ok'
  service: string
  version: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')

  useEffect(() => {
    const controller = new AbortController()

    async function checkApi() {
      try {
        const response = await fetch(`${API_BASE_URL}/health`, {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        })
        if (!response.ok) {
          throw new Error(`Health request returned ${String(response.status)}`)
        }
        const health = (await response.json()) as HealthResponse
        setApiState(health.status === 'ok' ? 'available' : 'unavailable')
      } catch (error: unknown) {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setApiState('unavailable')
      }
    }

    void checkApi()
    return () => controller.abort()
  }, [])

  return (
    <main>
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Drug safety intelligence</p>
        <h1 id="page-title">PharmaSense</h1>
        <p className="tagline">Detect patterns. Evaluate signals. Explore evidence.</p>
        <p className="summary">
          A research platform for studying potential reporting signals in public FDA data.
        </p>
      </section>

      <section className="status-card" aria-labelledby="foundation-status">
        <div>
          <p className="eyebrow">Phase 0</p>
          <h2 id="foundation-status">Engineering foundation</h2>
        </div>
        <p className={`status status--${apiState}`} role="status" aria-live="polite">
          API {apiState}
        </p>
      </section>

      <aside className="notice" aria-label="Research use notice">
        <strong>Research use only.</strong> PharmaSense does not establish causation, incidence,
        or comparative drug safety and must not be used for clinical decision-making.
      </aside>
    </main>
  )
}
