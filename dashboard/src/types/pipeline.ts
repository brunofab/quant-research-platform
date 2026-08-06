export type PipelineRunStatus =
  | 'running'
  | 'succeeded'
  | 'partial'
  | 'failed'

export type DataQualityRunStatus =
  | 'running'
  | 'passed'
  | 'warning'
  | 'failed'

export type PipelineRun = {
  id: number
  run_type: string
  status: PipelineRunStatus
  started_at: string
  finished_at: string | null
  companies_total: number
  companies_succeeded: number
  companies_failed: number
  records_inserted: number
  error_message: string | null
}

export type DataQualityRun = {
  id: number
  pipeline_run_id: number | null
  dataset: string
  source: string | null
  scope_type: string
  scope_key: string | null
  status: DataQualityRunStatus
  started_at: string
  finished_at: string | null
  checks_executed: number
  records_checked: number
  issues_found: number
  blocking_issues: number
  error_message: string | null
}

export type DataQualitySeverity =
  | 'info'
  | 'warning'
  | 'error'
  | 'critical'

export type DataQualityIssue = {
  id: number
  data_quality_run_id: number
  company_id: number | null
  entity_type: string
  entity_key: string
  dataset: string
  metric: string | null
  check_name: string
  severity: DataQualitySeverity
  blocking: boolean
  period_start: string | null
  period_end: string | null
  observed_at: string | null
  available_at: string | null
  actual_value: string | null
  expected_value: string | null
  message: string
  context_json: Record<string, unknown> | null
  created_at: string
}

export type DataQualityIssuesResponse = {
  run: DataQualityRun
  filters: {
    severity: DataQualitySeverity | null
    check_name: string | null
    ticker: string | null
    blocking_only: boolean
    limit: number
  }
  total_issues: number
  returned_issues: number
  issues: DataQualityIssue[]
}

export type PipelineStatusResponse = {
  pipeline: string
  has_run: boolean
  latest_run: PipelineRun | null
  last_successful_run: PipelineRun | null
  data_quality: DataQualityRun | null
}

export type DataQualityCheckStatus =
  | 'passed'
  | 'warning'
  | 'failed'

export type DataQualityCheckSummary = {
  dataset: string
  check_name: string
  execution_order: number
  status: DataQualityCheckStatus
  result_rows: number
  companies_checked: number
  records_checked: number
  issues_found: number
  blocking_issues: number
  duration_ms: number
  maximum_duration_ms: number
}

export type DataQualityChecksResponse = {
  run: DataQualityRun
  total_checks: number
  total_result_rows: number
  checks: DataQualityCheckSummary[]
}