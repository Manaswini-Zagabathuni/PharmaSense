import { render, screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'

import { App } from '../App'

const liveEnabled = import.meta.env.VITE_LIVE_E2E === '1'

describe.skipIf(!liveEnabled)('live full-stack dashboard', () => {
  test('renders seeded signals, detail, drugs, and reactions from the live API', async () => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL
    const health = await fetch(`${baseUrl}/health`)
    const readiness = await fetch(`${baseUrl}/ready`)
    expect(health.status).toBe(200)
    expect(readiness.status).toBe(200)

    render(<App />)

    const signalDrug = await screen.findByText('DEMO DRUG ALPHA', {}, { timeout: 15_000 })
    const signalRow = signalDrug.closest('tr')
    expect(signalRow).not.toBeNull()
    within(signalRow as HTMLTableRowElement).getByRole('button', { name: 'Inspect' }).click()
    expect(await screen.findByText('Contingency counts')).toBeInTheDocument()
    expect(screen.getByText('Prioritized')).toBeInTheDocument()

    screen.getByRole('button', { name: 'Drugs' }).click()
    const listedDrug = await screen.findByText('DEMO DRUG ALPHA', {}, { timeout: 15_000 })
    const drugRow = listedDrug.closest('tr')
    expect(drugRow).not.toBeNull()
    within(drugRow as HTMLTableRowElement)
      .getByRole('button', { name: 'View reactions' })
      .click()
    expect(await screen.findByText('DEMO REACTION ALPHA')).toBeInTheDocument()
    expect(screen.getByText(/Co-reporting does not establish causality/)).toBeInTheDocument()
  }, 30_000)
})
