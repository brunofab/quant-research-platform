import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

import type {
  DataQualityCheckSummary,
  DataQualityChecksResponse,
  DataQualityRunHistoryItem,
  DataQualityRunsResponse,
} from '../types/pipeline'

function formatDateTime(
  value: string | null,
): string {
  if (!value) {
    return '—'
  }

  return new Intl.DateTimeFormat(
    'de-AT',
    {
      dateStyle: 'medium',
      timeStyle: 'short',
    },
  ).format(new Date(value))
}

function checkLabel(
  checkName: string,
): string {
  const labels: Record<string, string> = {
    missing_required_metrics:
      'Missing required metrics',
    duplicate_latest_observation:
      'Duplicate latest observation',
    fcf_reconciliation:
      'FCF reconciliation',
    lineage_completeness:
      'Lineage completeness',
    fiscal_period_consistency:
      'Fiscal-period consistency',
    latest_period_freshness:
      'Latest-period freshness',
    latest_source_freshness:
      'Latest-source freshness',
  }

  return (
    labels[checkName] ??
    checkName.replaceAll('_', ' ')
  )
}

function statusClassName(
  status: string,
): string {
  return (
    'home-quality-status ' +
    `home-quality-status-${status}`
  )
}

function DataQualityPage() {
  const [
    runs,
    setRuns,
  ] = useState<DataQualityRunHistoryItem[]>(
    [],
  )

  const [
    selectedRunId,
    setSelectedRunId,
  ] = useState<number | null>(null)

  const [
    checks,
    setChecks,
  ] = useState<DataQualityCheckSummary[]>(
    [],
  )

  const [
    runsLoading,
    setRunsLoading,
  ] = useState(true)

  const [
    checksLoading,
    setChecksLoading,
  ] = useState(false)

  const [
    error,
    setError,
  ] = useState<string | null>(null)

  const selectedRun = useMemo(
    () =>
      runs.find(
        (run) => run.id === selectedRunId,
      ) ?? null,
    [runs, selectedRunId],
  )

  const loadRuns = useCallback(
    async (): Promise<void> => {
      setRunsLoading(true)
      setError(null)

      try {
        const response = await fetch(
          '/api/v1/data-quality/runs?limit=20',
        )

        if (!response.ok) {
          throw new Error(
            (
              'Run-history API returned ' +
              `HTTP ${response.status}`
            ),
          )
        }

        const payload =
          await response.json() as
            DataQualityRunsResponse

        setRuns(payload.runs)

        setSelectedRunId(
          (currentRunId) => {
            const currentStillExists =
              payload.runs.some(
                (run) =>
                  run.id === currentRunId,
              )

            if (currentStillExists) {
              return currentRunId
            }

            const latestDetailedRun =
              payload.runs.find(
                (run) =>
                  run.check_result_rows > 0,
              )

            return (
              latestDetailedRun?.id ??
              payload.runs[0]?.id ??
              null
            )
          },
        )
      } catch (requestError) {
        setRuns([])
        setSelectedRunId(null)
        setChecks([])

        setError(
          requestError instanceof Error
            ? requestError.message
            : 'Unable to load quality runs.',
        )
      } finally {
        setRunsLoading(false)
      }
    },
    [],
  )

  const loadChecks = useCallback(
    async (
      runId: number,
    ): Promise<void> => {
      setChecksLoading(true)
      setError(null)

      try {
        const response = await fetch(
          (
            '/api/v1/data-quality/runs/' +
            `${runId}/checks`
          ),
        )

        if (!response.ok) {
          throw new Error(
            (
              'Quality-check API returned ' +
              `HTTP ${response.status}`
            ),
          )
        }

        const payload =
          await response.json() as
            DataQualityChecksResponse

        setChecks(payload.checks)
      } catch (requestError) {
        setChecks([])

        setError(
          requestError instanceof Error
            ? requestError.message
            : 'Unable to load check results.',
        )
      } finally {
        setChecksLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    void loadRuns()
  }, [loadRuns])

  useEffect(() => {
    if (selectedRunId === null) {
      setChecks([])
      return
    }

    const run = runs.find(
      (candidate) =>
        candidate.id === selectedRunId,
    )

    if (
      run &&
      run.check_result_rows === 0
    ) {
      setChecks([])
      return
    }

    void loadChecks(selectedRunId)
  }, [
    loadChecks,
    runs,
    selectedRunId,
  ])

  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">
            Platform controls
          </p>

          <h1>
            Data Quality
          </h1>

          <p className="subtitle">
            Historical validation runs,
            individual controls and diagnostic
            findings.
          </p>
        </div>

        <button
          className="apply-button"
          type="button"
          disabled={
            runsLoading ||
            checksLoading
          }
          onClick={() => {
            void loadRuns()
          }}
        >
          Refresh history
        </button>
      </header>

      <section className="dashboard-card">
        <div className="card-header quality-run-header">
          <div>
            <p className="eyebrow">
              Run history
            </p>

            <h2>
              Validation run
            </h2>

            <p>
              Select a recent run to inspect
              its persisted check results.
            </p>
          </div>

          <label className="quality-run-selector">
            <span>
              Selected run
            </span>

            <select
              value={selectedRunId ?? ''}
              disabled={
                runsLoading ||
                runs.length === 0
              }
              onChange={(event) => {
                const value =
                  event.target.value

                setSelectedRunId(
                  value
                    ? Number(value)
                    : null,
                )
              }}
            >
              {runs.map((run) => (
                <option
                  key={run.id}
                  value={run.id}
                >
                  {`Run #${run.id} · `}
                  {formatDateTime(
                    run.started_at,
                  )}
                  {` · ${run.status}`}
                  {run.check_result_rows === 0
                    ? ' · legacy'
                    : ''}
                </option>
              ))}
            </select>
          </label>
        </div>

        {runsLoading && (
          <div className="home-placeholder">
            Loading validation history…
          </div>
        )}

        {!runsLoading && error && (
          <div className="home-quality-error">
            {error}
          </div>
        )}

        {!runsLoading &&
          !error &&
          !selectedRun && (
            <div className="home-placeholder">
              No data-quality runs are
              available.
            </div>
          )}

        {!runsLoading &&
          !error &&
          selectedRun && (
            <div className="quality-summary-grid">
              <div className="quality-summary-metric">
                <span>
                  Status
                </span>

                <strong>
                  <span
                    className={
                      statusClassName(
                        selectedRun.status,
                      )
                    }
                  >
                    {selectedRun.status}
                  </span>
                </strong>
              </div>

              <div className="quality-summary-metric">
                <span>
                  Started
                </span>

                <strong>
                  {formatDateTime(
                    selectedRun.started_at,
                  )}
                </strong>
              </div>

              <div className="quality-summary-metric">
                <span>
                  Checks executed
                </span>

                <strong>
                  {selectedRun.checks_executed
                    .toLocaleString('de-AT')}
                </strong>
              </div>

              <div className="quality-summary-metric">
                <span>
                  Records checked
                </span>

                <strong>
                  {selectedRun.records_checked
                    .toLocaleString('de-AT')}
                </strong>
              </div>

              <div className="quality-summary-metric">
                <span>
                  Issues
                </span>

                <strong>
                  {selectedRun.issues_found
                    .toLocaleString('de-AT')}
                </strong>
              </div>

              <div className="quality-summary-metric">
                <span>
                  Blocking issues
                </span>

                <strong>
                  {selectedRun.blocking_issues
                    .toLocaleString('de-AT')}
                </strong>
              </div>
            </div>
          )}
      </section>

      <section className="dashboard-card quality-checks-card">
        <div className="card-header">
          <div>
            <p className="eyebrow">
              Persisted controls
            </p>

            <h2>
              Check results
            </h2>

            <p>
              Aggregated results across all
              companies included in the run.
            </p>
          </div>

          <span className="company-count">
            {checks.length > 0
              ? `${checks.length} checks`
              : 'No details'}
          </span>
        </div>

        {selectedRun &&
          selectedRun.check_result_rows ===
            0 && (
            <div className="quality-legacy-note">
              This run predates persistent
              per-check results. Its aggregate
              run totals remain available, but
              individual controls cannot be
              reconstructed.
            </div>
          )}

        {checksLoading && (
          <div className="home-placeholder">
            Loading check results…
          </div>
        )}

        {!checksLoading &&
          selectedRun &&
          selectedRun.check_result_rows > 0 &&
          checks.length === 0 &&
          !error && (
            <div className="home-placeholder">
              No persisted checks were returned
              for this run.
            </div>
          )}

        {!checksLoading &&
          checks.length > 0 && (
            <div className="home-quality-table-wrapper">
              <table className="home-quality-table">
                <thead>
                  <tr>
                    <th>Check</th>
                    <th>Status</th>
                    <th>Companies</th>
                    <th>Records</th>
                    <th>Issues</th>
                    <th>Blocking</th>
                    <th>Total time</th>
                    <th>Max time</th>
                  </tr>
                </thead>

                <tbody>
                  {checks.map((check) => (
                    <tr key={check.check_name}>
                      <td>
                        <strong>
                          {checkLabel(
                            check.check_name,
                          )}
                        </strong>

                        <span>
                          {check.dataset}
                        </span>
                      </td>

                      <td>
                        <span
                          className={
                            statusClassName(
                              check.status,
                            )
                          }
                        >
                          {check.status}
                        </span>
                      </td>

                      <td>
                        {check.companies_checked
                          .toLocaleString('de-AT')}
                      </td>

                      <td>
                        {check.records_checked
                          .toLocaleString('de-AT')}
                      </td>

                      <td>
                        {check.issues_found
                          .toLocaleString('de-AT')}
                      </td>

                      <td>
                        {check.blocking_issues
                          .toLocaleString('de-AT')}
                      </td>

                      <td>
                        {check.duration_ms
                          .toLocaleString('de-AT')}
                        {' ms'}
                      </td>

                      <td>
                        {check.maximum_duration_ms
                          .toLocaleString('de-AT')}
                        {' ms'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </section>
    </main>
  )
}

export default DataQualityPage