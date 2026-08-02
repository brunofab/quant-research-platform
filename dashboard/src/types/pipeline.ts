export type PipelineRunStatus =
  | 'running'
  | 'succeeded'
  | 'partial'
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

export type PipelineStatusResponse = {
  pipeline: string
  has_run: boolean
  latest_run: PipelineRun | null
  last_successful_run: PipelineRun | null
}
