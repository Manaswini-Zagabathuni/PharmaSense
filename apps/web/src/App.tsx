import { useEffect, useState } from 'react'

import { type AnalysisWorkspace, replaceBrowserUrl, workspaceFromSearch, workspaceUrl } from './analysisUrlState'
import { DrugExplorer } from './components/DrugExplorer'
import { HistoricalTrends } from './components/HistoricalTrends'
import { ProjectOverview } from './components/ProjectOverview'
import { SignalComparison } from './components/SignalComparison'
import { SignalExplorer } from './components/SignalExplorer'

export function App() {
  const [workspace, setWorkspace] = useState<AnalysisWorkspace>(() =>
    workspaceFromSearch(window.location.search),
  )

  useEffect(() => {
    function restoreWorkspace() {
      setWorkspace(workspaceFromSearch(window.location.search))
    }
    window.addEventListener('popstate', restoreWorkspace)
    return () => window.removeEventListener('popstate', restoreWorkspace)
  }, [])

  function selectWorkspace(nextWorkspace: AnalysisWorkspace) {
    setWorkspace(nextWorkspace)
    replaceBrowserUrl(workspaceUrl(nextWorkspace))
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a
          className="brand"
          href="/"
          aria-label="PharmaSense overview"
          onClick={(event) => {
            event.preventDefault()
            selectWorkspace('overview')
          }}
        >
          <span className="brand-mark" aria-hidden="true">P</span>
          <span><strong>PharmaSense</strong><small>Drug safety intelligence</small></span>
        </a>
        <nav className="primary-nav" aria-label="Analytics workspaces">
          <button type="button" aria-current={workspace === 'overview' ? 'page' : undefined} onClick={() => selectWorkspace('overview')}>Overview</button>
          <button type="button" aria-current={workspace === 'signals' ? 'page' : undefined} onClick={() => selectWorkspace('signals')}>Signals</button>
          <button type="button" aria-current={workspace === 'drugs' ? 'page' : undefined} onClick={() => selectWorkspace('drugs')}>Drugs</button>
          <button type="button" aria-current={workspace === 'historical' ? 'page' : undefined} onClick={() => selectWorkspace('historical')}>Historical Trends</button>
          <button type="button" aria-current={workspace === 'comparison' ? 'page' : undefined} onClick={() => selectWorkspace('comparison')}>Signal Comparison</button>
        </nav>
        <span className="read-only-badge">Read-only research</span>
      </header>

      <aside className="research-banner" aria-label="Research use notice">
        <strong>Research use only.</strong>
        <span>FAERS has important limitations. Statistical signals and co-reported events do not establish causality or incidence. PharmaSense is not for clinical decision-making.</span>
      </aside>

      <main id="main-content">
        {workspace === 'overview' && <ProjectOverview onNavigate={selectWorkspace} />}
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
