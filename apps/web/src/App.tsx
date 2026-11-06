import { useState } from 'react'

import { DrugExplorer } from './components/DrugExplorer'
import { HistoricalTrends } from './components/HistoricalTrends'
import { SignalComparison } from './components/SignalComparison'
import { SignalExplorer } from './components/SignalExplorer'

type Workspace = 'signals' | 'drugs' | 'historical' | 'comparison'

export function App() {
  const [workspace, setWorkspace] = useState<Workspace>('signals')

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#main-content" aria-label="PharmaSense home">
          <span className="brand-mark" aria-hidden="true">P</span>
          <span><strong>PharmaSense</strong><small>Drug safety intelligence</small></span>
        </a>
        <nav className="primary-nav" aria-label="Analytics workspaces">
          <button type="button" aria-current={workspace === 'signals' ? 'page' : undefined} onClick={() => setWorkspace('signals')}>Signals</button>
          <button type="button" aria-current={workspace === 'drugs' ? 'page' : undefined} onClick={() => setWorkspace('drugs')}>Drugs</button>
          <button type="button" aria-current={workspace === 'historical' ? 'page' : undefined} onClick={() => setWorkspace('historical')}>Historical Trends</button>
          <button type="button" aria-current={workspace === 'comparison' ? 'page' : undefined} onClick={() => setWorkspace('comparison')}>Signal Comparison</button>
        </nav>
        <span className="read-only-badge">Read-only research</span>
      </header>

      <aside className="research-banner" aria-label="Research use notice">
        <strong>Research use only.</strong>
        <span>FAERS has important limitations. Statistical signals and co-reported events do not establish causality or incidence. PharmaSense is not for clinical decision-making.</span>
      </aside>

      <main id="main-content">
        {workspace === 'signals' && <SignalExplorer />}
        {workspace === 'drugs' && <DrugExplorer />}
        {workspace === 'historical' && <HistoricalTrends />}
        {workspace === 'comparison' && <SignalComparison />}
      </main>

      <footer>
        <p>PharmaSense · Detect patterns. Evaluate signals. Explore evidence.</p>
        <p>Public FDA reporting data · Research interpretation required</p>
      </footer>
    </div>
  )
}
