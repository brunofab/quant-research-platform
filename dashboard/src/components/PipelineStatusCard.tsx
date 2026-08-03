import DataQualityIssuesPanel from './DataQualityIssuesPanel'
import type {
  DataQualityRunStatus,
  PipelineRun,
  PipelineRunStatus,
  PipelineStatusResponse,
} from '../types/pipeline'

type PipelineStatusCardProps = {
  data: PipelineStatusResponse | null
  loading: boolean
  error: string | null
}

function formatDate(
  value: string | null | undefined,
): string {
  if (!value) {
    return '—'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('de-AT', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function statusLabel(
  status: PipelineRunStatus,
): string {
  switch (status) {
    case 'running':
      return 'Pipeline running'
    case 'succeeded':
      return 'Pipeline healthy'
    case 'partial':
      return 'Partial failure'
    case 'failed':
      return 'Pipeline failed'
  }
}

function statusClassName(
  status: PipelineRunStatus,
): string {
  return (
    'pipeline-status-badge ' +
    `pipeline-status-${status}`
  )
}

function qualityStatusLabel(
  status: DataQualityRunStatus,
): string {
  switch (status) {
    case 'running':
      return 'Quality checks running'
    case 'passed':
      return 'Data quality passed'
    case 'warning':
      return 'Data quality warning'
    case 'failed':
      return 'Data quality failed'
  }
}

function qualityStatusClassName(
  status: DataQualityRunStatus,
): string {
  return (
    'data-quality-status-badge ' +
    `data-quality-status-${status}`
  )
}

function completedAt(
  run: PipelineRun | null,
): string {
  if (!run) {
    return '—'
  }

  return formatDate(
    run.finished_at ?? run.started_at,
  )
}

function PipelineStatusCard({
  data,
  loading,
  error,
}: PipelineStatusCardProps) {
  if (loading) {
    return (
      <section className="pipeline-status-card">
        <div className="pipeline-status-message">
          <span className="pipeline-status-spinner" />

          Checking pipeline status…
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="pipeline-status-card pipeline-status-card-error">
        <div className="pipeline-status-empty-content">
          <p className="pipeline-status-eyebrow">
            Data pipeline
          </p>

          <h2>Status unavailable</h2>

          <p className="pipeline-status-error-text">
            {error}
          </p>
        </div>
      </section>
    )
  }

  if (
    !data ||
    !data.has_run ||
    !data.latest_run
  ) {
    return (
      <section className="pipeline-status-card">
        <div className="pipeline-status-empty-content">
          <p className="pipeline-status-eyebrow">
            Data pipeline
          </p>

          <h2>No refresh recorded</h2>

          <p className="pipeline-status-description">
            The pipeline has not completed a tracked
            refresh yet.
          </p>
        </div>
      </section>
    )
  }

  const latestRun = data.latest_run
  const lastSuccessfulRun =
    data.last_successful_run
  const qualityRun = data.data_quality

  const displayedRefresh =
    latestRun.status === 'succeeded'
      ? latestRun
      : lastSuccessfulRun

  const qualityUnavailableLabel =
    latestRun.status === 'running'
      ? 'Pending'
      : 'Not available'

  const qualityUnavailableText =
    latestRun.status === 'running'
      ? (
          'The refresh is still running or its ' +
          'quality checks have not started yet.'
        )
      : (
          'No data-quality run is linked to this ' +
          'pipeline refresh.'
        )

  return (
    <section
      className={
        'pipeline-status-card ' +
        `pipeline-status-card-${latestRun.status}`
      }
    >
      <div className="pipeline-status-header">
        <div>
          <p className="pipeline-status-eyebrow">
            Data pipeline
          </p>

          <div className="pipeline-status-title-row">
            <h2>
              {statusLabel(latestRun.status)}
            </h2>

            <span
              className={statusClassName(
                latestRun.status,
              )}
            >
              {latestRun.status}
            </span>
          </div>

          <p className="pipeline-status-description">
            Latest tracked SEC ingestion,
            normalization and signal validation run.
          </p>
        </div>

        <span className="pipeline-run-id">
          Run #{latestRun.id}
        </span>
      </div>

      <div className="pipeline-status-grid">
        <div className="pipeline-status-metric">
          <span>Last successful refresh</span>

          <strong>
            {completedAt(displayedRefresh)}
          </strong>
        </div>

        <div className="pipeline-status-metric">
          <span>Companies succeeded</span>

          <strong>
            {latestRun.companies_succeeded} /{' '}
            {latestRun.companies_total}
          </strong>
        </div>

        <div className="pipeline-status-metric">
          <span>Records inserted</span>

          <strong>
            {latestRun.records_inserted.toLocaleString(
              'de-AT',
            )}
          </strong>
        </div>

        <div className="pipeline-status-metric">
          <span>Companies failed</span>

          <strong>
            {latestRun.companies_failed}
          </strong>
        </div>
      </div>

      {latestRun.status !== 'succeeded' &&
        lastSuccessfulRun && (
          <div className="pipeline-status-warning">
            The latest run did not fully succeed.
            Last successful run:{' '}
            {completedAt(lastSuccessfulRun)}.
          </div>
        )}

      {latestRun.error_message && (
        <details className="pipeline-error-details">
          <summary>Show pipeline error</summary>

          <pre>{latestRun.error_message}</pre>
        </details>
      )}

      <div
        className={
          'data-quality-section ' +
          (
            qualityRun
              ? (
                  'data-quality-section-' +
                  qualityRun.status
                )
              : 'data-quality-section-unavailable'
          )
        }
      >
        <div className="data-quality-header">
          <div>
            <p className="pipeline-status-eyebrow">
              Data quality
            </p>

            <div className="data-quality-title-row">
              <h3>
                {qualityRun
                  ? qualityStatusLabel(
                      qualityRun.status,
                    )
                  : qualityUnavailableLabel}
              </h3>

              {qualityRun ? (
                <span
                  className={qualityStatusClassName(
                    qualityRun.status,
                  )}
                >
                  {qualityRun.status}
                </span>
              ) : (
                <span className="data-quality-status-badge data-quality-status-unavailable">
                  unavailable
                </span>
              )}
            </div>

            <p className="data-quality-description">
              {qualityRun
                ? (
                    'Completeness, point-in-time ' +
                    'uniqueness and financial ' +
                    'reconciliation checks.'
                  )
                : qualityUnavailableText}
            </p>
          </div>

          {qualityRun && (
            <span className="data-quality-run-id">
              Quality #{qualityRun.id}
            </span>
          )}
        </div>

        {qualityRun && (
          <>
            <div className="data-quality-grid">
              <div className="data-quality-metric">
                <span>Checks executed</span>

                <strong>
                  {qualityRun.checks_executed
                    .toLocaleString('de-AT')}
                </strong>
              </div>

              <div className="data-quality-metric">
                <span>Records checked</span>

                <strong>
                  {qualityRun.records_checked
                    .toLocaleString('de-AT')}
                </strong>
              </div>

              <div className="data-quality-metric">
                <span>Issues found</span>

                <strong>
                  {qualityRun.issues_found
                    .toLocaleString('de-AT')}
                </strong>
              </div>

              <div className="data-quality-metric">
                <span>Blocking issues</span>

                <strong>
                  {qualityRun.blocking_issues
                    .toLocaleString('de-AT')}
                </strong>
              </div>
            </div>

            {qualityRun.issues_found > 0 && (
              <DataQualityIssuesPanel
                runId={qualityRun.id}
                totalIssues={qualityRun.issues_found}
              />
            )}

            {qualityRun.error_message && (
              <details className="data-quality-error-details">
                <summary>
                  Show data-quality error
                </summary>

                <pre>
                  {qualityRun.error_message}
                </pre>
              </details>
            )}
          </>
        )}
      </div>
    </section>
  )
}

export default PipelineStatusCard