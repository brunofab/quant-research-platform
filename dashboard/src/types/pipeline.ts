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

export type PipelineStatusResponse = {
  pipeline: string
  has_run: boolean
  latest_run: PipelineRun | null
  last_successful_run: PipelineRun | null
  data_quality: DataQualityRun | null
}