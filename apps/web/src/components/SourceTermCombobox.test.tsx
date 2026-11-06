import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'

import { SourceTermCombobox } from './SourceTermCombobox'

function jsonResponse(items: string[]): Response {
  return new Response(
    JSON.stringify({
      items: items.map((term) => ({ term })),
      returned_count: items.length,
      limit: 10,
      research_notice: 'Research only.',
      source_term_notice: 'Source derived.',
    }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  )
}

function Harness({ kind = 'drugs' }: { kind?: 'drugs' | 'reactions' }) {
  const [value, setValue] = useState('')
  return (
    <SourceTermCombobox
      id="term"
      label="Source term"
      kind={kind}
      value={value}
      onChange={setValue}
    />
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('loads bounded suggestions and supports keyboard selection', async () => {
  let resolveRequest: ((response: Response) => void) | undefined
  const fetchMock = vi.fn().mockImplementation(
    () =>
      new Promise<Response>((resolve) => {
        resolveRequest = resolve
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  render(<Harness />)

  const input = screen.getByRole('combobox', { name: 'Source term' })
  fireEvent.change(input, { target: { value: 'alp' } })

  expect(await screen.findByText('Loading suggestions…')).toBeInTheDocument()
  resolveRequest?.(jsonResponse(['ALPHA', 'ALPINE']))
  expect(await screen.findByRole('option', { name: 'ALPHA' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(fetchMock.mock.calls[0]?.[0]).toContain('/discovery/drugs?q=alp&limit=10')

  fireEvent.keyDown(input, { key: 'ArrowDown' })
  expect(screen.getByRole('option', { name: 'ALPHA' })).toHaveAttribute('aria-selected', 'true')
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(input).toHaveValue('ALPHA')
  expect(input).toHaveAttribute('aria-expanded', 'false')
})

test('preserves manual entry and does not request for short input', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  render(<Harness />)

  const input = screen.getByRole('combobox', { name: 'Source term' })
  fireEvent.change(input, { target: { value: 'x' } })

  expect(input).toHaveValue('x')
  expect(screen.getByText(/Enter at least 2 characters/)).toBeInTheDocument()
  await new Promise((resolve) => window.setTimeout(resolve, 300))
  expect(fetchMock).not.toHaveBeenCalled()
})

test('communicates empty results while preserving the manual value', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])))
  render(<Harness kind="reactions" />)

  const input = screen.getByRole('combobox', { name: 'Source term' })
  fireEvent.change(input, { target: { value: 'unknown event' } })

  expect(await screen.findByText(/No source-derived terms matched/)).toBeInTheDocument()
  expect(input).toHaveValue('unknown event')
})

test('communicates failures and allows a bounded retry', async () => {
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce(jsonResponse(['RECOVERED']))
  vi.stubGlobal('fetch', fetchMock)
  render(<Harness />)

  fireEvent.change(screen.getByRole('combobox', { name: 'Source term' }), {
    target: { value: 'recover' },
  })
  expect(await screen.findByRole('alert')).toHaveTextContent('Suggestions are unavailable')
  fireEvent.click(screen.getByRole('button', { name: 'Retry suggestions' }))

  expect(await screen.findByRole('option', { name: 'RECOVERED' })).toBeInTheDocument()
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
})
