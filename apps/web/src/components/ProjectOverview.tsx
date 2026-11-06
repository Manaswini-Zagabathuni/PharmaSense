import type { AnalysisWorkspace } from '../analysisUrlState'

type WorkspaceTarget = Exclude<AnalysisWorkspace, 'overview'>

interface ProjectOverviewProps {
  onNavigate: (workspace: WorkspaceTarget) => void
}

const CAPABILITIES: Array<{
  title: string
  description: string
  action: string
  target: WorkspaceTarget
  marker: string
}> = [
  {
    title: 'Signal Explorer',
    description:
      'Review prioritized drug–reaction reporting signals with server-calculated PRR, ROR, confidence intervals, and transparent eligibility diagnostics.',
    action: 'Open Signal Explorer',
    target: 'signals',
    marker: '01',
  },
  {
    title: 'Drug Explorer',
    description:
      'Browse source drug names and inspect their most frequently co-reported reaction terms without implying causality or clinical risk.',
    action: 'Open Drug Explorer',
    target: 'drugs',
    marker: '02',
  },
  {
    title: 'Historical Trends',
    description:
      'Evaluate the same drug–reaction pair independently across completed, loaded FAERS source-quarter ingestions.',
    action: 'Open Historical Trends',
    target: 'historical',
    marker: '03',
  },
  {
    title: 'Signal Comparison',
    description:
      'Place two to four observed pairs side by side while preserving server-derived values, diagnostics, and entered order.',
    action: 'Open Signal Comparison',
    target: 'comparison',
    marker: '04',
  },
  {
    title: 'Source-Term Discovery',
    description:
      'Find bounded, source-derived drug and reaction spellings while keeping manual entry available and avoiding automatic synonym claims.',
    action: 'Discover terms in Historical Trends',
    target: 'historical',
    marker: '05',
  },
  {
    title: 'Reproducible Analysis Links',
    description:
      'Bookmark or copy a validated analysis configuration. Reopening a link restores inputs and uses the data currently loaded.',
    action: 'Build a comparison link',
    target: 'comparison',
    marker: '06',
  },
]

const WORKFLOW = [
  ['Discover', 'Search bounded source-derived drug and reaction terms.'],
  ['Explore', 'Inspect resolved report counts, reaction profiles, and signal details.'],
  ['Analyze', 'Evaluate server-calculated reporting measurements and quarter trends.'],
  ['Compare', 'Review multiple explicitly selected drug–reaction pairs side by side.'],
  ['Reproduce', 'Share validated configuration links that can be rerun on loaded data.'],
] as const

export function ProjectOverview({ onNavigate }: ProjectOverviewProps) {
  return (
    <section className="project-overview" aria-labelledby="overview-title">
      <div className="overview-hero">
        <div className="overview-hero__copy">
          <p className="eyebrow">Drug safety intelligence</p>
          <h1 id="overview-title">Detect patterns. Evaluate signals. Explore evidence.</h1>
          <p className="overview-hero__lede">
            PharmaSense is a research-oriented pharmacovigilance analytics platform for exploring
            drug–reaction reporting patterns in loaded FDA FAERS source data.
          </p>
          <div className="overview-hero__actions">
            <button
              className="button button--primary"
              type="button"
              onClick={() => onNavigate('signals')}
            >
              Explore reporting signals
            </button>
            <button
              className="button button--secondary"
              type="button"
              onClick={() => onNavigate('historical')}
            >
              Analyze historical trends
            </button>
          </div>
        </div>
        <aside className="overview-principles" aria-label="Platform principles">
          <p className="eyebrow">Built for traceable research</p>
          <dl>
            <div><dt>Source</dt><dd>Official FDA FAERS quarterly extracts</dd></div>
            <div><dt>Population</dt><dd>Unambiguously resolved latest report versions</dd></div>
            <div><dt>Interpretation</dt><dd>Reporting signals, never causal conclusions</dd></div>
          </dl>
        </aside>
      </div>

      <section className="overview-section" aria-labelledby="capabilities-title">
        <div className="overview-section__heading">
          <div>
            <p className="eyebrow">Existing workspaces</p>
            <h2 id="capabilities-title">A focused path from source terms to evidence</h2>
          </div>
          <p>Each capability opens an existing read-only analytics flow.</p>
        </div>
        <div className="capability-grid">
          {CAPABILITIES.map((capability) => (
            <article className="capability-card" key={capability.title}>
              <span className="capability-card__marker" aria-hidden="true">{capability.marker}</span>
              <h3>{capability.title}</h3>
              <p>{capability.description}</p>
              <button
                className="text-button"
                type="button"
                onClick={() => onNavigate(capability.target)}
              >
                {capability.action}
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="overview-section workflow-section" aria-labelledby="workflow-title">
        <div className="overview-section__heading">
          <div>
            <p className="eyebrow">Analytics workflow</p>
            <h2 id="workflow-title">Discover → Explore → Analyze → Compare → Reproduce</h2>
          </div>
        </div>
        <ol className="workflow-list">
          {WORKFLOW.map(([stage, description], index) => (
            <li key={stage}>
              <span aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
              <div><h3>{stage}</h3><p>{description}</p></div>
            </li>
          ))}
        </ol>
      </section>

      <aside className="overview-science-notice" aria-labelledby="overview-limitations-title">
        <p className="eyebrow">Scientific boundary</p>
        <h2 id="overview-limitations-title">Reporting evidence requires careful interpretation</h2>
        <p>
          FAERS is a spontaneous reporting system. Reporting patterns and disproportionality
          metrics do not establish causality, incidence, or clinical risk. PharmaSense supports
          research and exploratory analysis only; it is not for clinical decision-making.
        </p>
      </aside>
    </section>
  )
}
