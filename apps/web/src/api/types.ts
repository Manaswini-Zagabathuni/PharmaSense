export type UndefinedMetricReason =
  | 'EMPTY_POPULATION'
  | 'NO_DRUG_REPORTS'
  | 'NO_NON_DRUG_REPORTS'
  | 'ZERO_COMPARATOR_REACTION_COUNT'
  | 'ZERO_DRUG_NON_REACTION_COUNT'
  | 'ZERO_NON_DRUG_REACTION_COUNT'
  | 'ZERO_CELL_CONFIDENCE_INTERVAL'
  | 'NON_FINITE_RESULT'

export type SignalEligibilityReason =
  | 'PAIR_NOT_OBSERVED'
  | 'BELOW_MINIMUM_PAIR_REPORTS'
  | 'BELOW_MINIMUM_POPULATION'
  | 'PRR_UNDEFINED'
  | 'ROR_UNDEFINED'
  | 'ROR_CONFIDENCE_INTERVAL_UNDEFINED'

export type PriorityExclusionReason =
  | 'NOT_ELIGIBLE'
  | 'LOWER_CONFIDENCE_BOUND_NOT_ABOVE_MINIMUM'

export interface MetricEstimate {
  value: number | null
  undefined_reason: UndefinedMetricReason | null
}

export interface RorConfidenceInterval {
  confidence_level: number
  lower_bound: number | null
  upper_bound: number | null
  undefined_reason: UndefinedMetricReason | null
}

export interface SignalThresholds {
  minimum_pair_reports: number
  minimum_population: number | null
  minimum_ror_lower_bound: number
}

export interface Signal {
  drug_name: string
  reaction_term: string
  analysis_population: number
  a: number
  b: number
  c: number
  d: number
  prr: MetricEstimate
  ror: MetricEstimate
  ror_confidence_interval: RorConfidenceInterval
  thresholds: SignalThresholds
  is_observed: boolean
  metrics_calculable: boolean
  statistically_evaluable: boolean
  eligible_for_prioritization: boolean
  ineligibility_reasons: SignalEligibilityReason[]
  is_prioritized: boolean
  priority_exclusion_reason: PriorityExclusionReason | null
}

export interface SignalListResponse {
  items: Signal[]
  returned_count: number
  limit: number
  research_notice: string
}

export interface SignalDetailResponse {
  signal: Signal
  research_notice: string
}

export interface DrugSummary {
  drug_name: string
  report_count: number
  case_count: number
}

export interface DrugListResponse {
  items: DrugSummary[]
  returned_count: number
  limit: number
  offset: number
  research_notice: string
}

export interface DrugReactionSummary {
  drug_name: string
  reaction_term: string
  report_count: number
  case_count: number
}

export interface DrugReactionListResponse {
  drug_name: string
  items: DrugReactionSummary[]
  returned_count: number
  limit: number
  research_notice: string
}

export interface SourceTerm {
  term: string
}

export interface TermDiscoveryResponse {
  items: SourceTerm[]
  returned_count: number
  limit: number
  research_notice: string
  source_term_notice: string
}

export type HistoricalPopulationSelectionRule =
  'COMPLETED_INGESTIONS_IN_INCLUSIVE_QUARTER_RANGE'

export interface SourceSnapshot {
  source_quarter: string
  source_name: string
  filename: string
  archive_sha256: string
  retrieved_at: string
  known_in_provenance: boolean
  completed_ingestion_runs: number
  latest_completed_at: string | null
  persisted_report_count: number
  successfully_loaded_report_count: number
  successfully_loaded_case_count: number
  contains_successfully_loaded_reports: boolean
}

export interface SourceSnapshotListResponse {
  items: SourceSnapshot[]
  returned_count: number
  limit: number
}

export interface HistoricalAnalysisMetadata {
  selection_rule: HistoricalPopulationSelectionRule
  requested_start_quarter: string
  requested_end_quarter: string
  selected_source_quarters: string[]
  resolved_report_count: number
  resolved_case_count: number
  excluded_invalid_version_case_count: number
  excluded_version_tie_case_count: number
}

export interface QuarterSignal {
  source_quarter: string
  signal: Signal
}

export interface HistoricalSignalResponse {
  metadata: HistoricalAnalysisMetadata
  items: QuarterSignal[]
  returned_count: number
  research_notice: string
  historical_method_notice: string
}

export interface ErrorResponse {
  detail: string
}
