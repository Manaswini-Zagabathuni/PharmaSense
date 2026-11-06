import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { AnalysisLinkControl } from './AnalysisLinkControl'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function installClipboard(writeText: (value: string) => Promise<void>) {
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  })
}

test('copies the accessible analysis URL and reports success', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined)
  installClipboard(writeText)
  const url = new URL('https://example.test/?workspace=historical&drug=A')
  render(<AnalysisLinkControl url={url} />)

  fireEvent.click(screen.getByRole('button', { name: 'Copy analysis link' }))

  await waitFor(() => expect(writeText).toHaveBeenCalledWith(url.href))
  expect(screen.getByRole('status')).toHaveTextContent('Analysis configuration link copied.')
  expect(screen.getByText(/reruns the analysis against currently loaded data/)).toBeInTheDocument()
})

test('reports clipboard failures without claiming success', async () => {
  installClipboard(vi.fn().mockRejectedValue(new Error('denied')))
  render(<AnalysisLinkControl url={new URL('https://example.test/?workspace=comparison')} />)

  fireEvent.click(screen.getByRole('button', { name: 'Copy analysis link' }))

  expect(await screen.findByText('Unable to copy the analysis link.')).toBeInTheDocument()
  expect(screen.queryByText('Analysis configuration link copied.')).not.toBeInTheDocument()
})

test('disables copying until configuration is valid', () => {
  render(<AnalysisLinkControl url={null} />)

  expect(screen.getByRole('button', { name: 'Copy analysis link' })).toBeDisabled()
  expect(screen.getByRole('status')).toHaveTextContent('Complete a valid configuration')
})
