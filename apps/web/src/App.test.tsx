import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from './App'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('renders the project identity and research disclaimer', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok', service: 'pharmasense-api', version: '0.1.0' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )

  render(<App />)

  expect(screen.getByRole('heading', { name: 'PharmaSense' })).toBeInTheDocument()
  expect(screen.getByText(/Research use only/i)).toBeInTheDocument()
  expect(await screen.findByText('API available')).toBeInTheDocument()
})

test('reports an unavailable API without hiding the application', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))

  render(<App />)

  expect(await screen.findByText('API unavailable')).toBeInTheDocument()
  expect(screen.getByText(/potential reporting signals/i)).toBeInTheDocument()
})

test('reports an unavailable API for a non-success response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 503 })))

  render(<App />)

  expect(await screen.findByText('API unavailable')).toBeInTheDocument()
})

test('rejects an unexpected health payload', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'unexpected' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )

  render(<App />)

  expect(await screen.findByText('API unavailable')).toBeInTheDocument()
})

test('aborts an in-flight health request when unmounted', async () => {
  let requestWasAborted = false
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            requestWasAborted = true
            reject(new DOMException('Request aborted', 'AbortError'))
          })
        }),
    ),
  )

  const view = render(<App />)
  view.unmount()
  await Promise.resolve()

  expect(requestWasAborted).toBe(true)
})
