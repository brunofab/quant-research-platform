import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

import type {
  DataQualityCheckSummary,
  DataQualityChecksResponse,
  DataQualityIssue,
  DataQualityIssuesResponse,
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

function formatPeriod(
  periodStart: string | null,
  periodEnd: string | null,
): string {
  if (periodStart && periodEnd) {
    return `${periodStart} → ${periodEnd}`
  }

  return periodEnd ?? periodStart ?? '—'
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

    const [
    selectedCheckName,
    setSelectedCheckName,
  ] = useState<string | null>(null)

  const [
    issues,
    setIssues,
  ] = useState<DataQualityIssue[]>([])

  const [
    totalIssues,
    setTotalIssues,
  ] = useState(0)

  const [
    issuesLoading,
    setIssuesLoading,
  ] = useState(false)

  const [
    issuesError,
    setIssuesError,
  ] = useState<string | null>(null)

  const selectedRun = useMemo(
    () =>
      runs.find(
        (run) => run.id === selectedRunId,
      ) ?? null,
    [runs, selectedRunId],
  )

  const selectedCheck = useMemo(
    () =>
      checks.find(
        (check) =>
          check.check_name ===
          selectedCheckName,
      ) ?? null,
    [checks, selectedCheckName],
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

  const loadIssues = useCallback(
    async (
      runId: number,
      checkName: string,
    ): Promise<void> => {
      setIssuesLoading(true)
      setIssuesError(null)

      try {
        const parameters =
          new URLSearchParams({
            check_name: checkName,
            limit: '200',
          })

        const response = await fetch(
          (
            '/api/v1/data-quality/runs/' +
            `${runId}/issues?${parameters}`
          ),
        )

        if (!response.ok) {
          throw new Error(
            (
              'Quality-issues API returned ' +
              `HTTP ${response.status}`
            ),
          )
        }

        const payload =
          await response.json() as
            DataQualityIssuesResponse

        setIssues(payload.issues)
        setTotalIssues(payload.total_issues)
      } catch (requestError) {
        setIssues([])
        setTotalIssues(0)

        setIssuesError(
          requestError instanceof Error
            ? requestError.message
            : 'Unable to load findings.',
        )
      } finally {
        setIssuesLoading(false)
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

    useEffect(() => {
    setSelectedCheckName(null)
    setIssues([])
    setTotalIssues(0)
    setIssuesError(null)
  }, [selectedRunId])

  useEffect(() => {
    if (
      selectedRunId === null ||
      selectedCheckName === null
    ) {
      setIssues([])
      setTotalIssues(0)
      setIssuesError(null)
      return
    }

    void loadIssues(
      selectedRunId,
      selectedCheckName,
    )
  }, [
    loadIssues,
    selectedCheckName,
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
                  {checks.map((check) => {
                    const isSelected =
                      check.check_name === selectedCheckName

                    const selectCheck = (): void => {
                      setSelectedCheckName(
                        isSelected
                          ? null
                          : check.check_name,
                      )
                    }

                    return (
                      <tr
                        key={check.check_name}
                        className={
                          isSelected
                            ? (
                                'quality-check-row ' +
                                'quality-check-row-selected'
                              )
                            : 'quality-check-row'
                        }
                        role="button"
                        tabIndex={0}
                        aria-selected={isSelected}
                        onClick={selectCheck}
                        onKeyDown={(event) => {
                          if (
                            event.key === 'Enter' ||
                            event.key === ' '
                          ) {
                            event.preventDefault()
                            selectCheck()
                          }
                        }}
                      >
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
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
                  {selectedCheck && (
          <div className="quality-issues-panel">
            <button
              className="quality-issues-toggle"
              type="button"
              onClick={() => {
                setSelectedCheckName(null)
              }}
            >
              <span>
                {checkLabel(
                  selectedCheck.check_name,
                )}
                {' · Findings'}
              </span>

              <span className="quality-issues-count">
                {issuesLoading
                  ? '…'
                  : totalIssues.toLocaleString(
                      'de-AT',
                    )}
              </span>
            </button>

            <div className="quality-issues-content">
              {issuesLoading && (
                <div className="quality-issues-state">
                  <span className="pipeline-status-spinner" />

                  Loading diagnostic findings…
                </div>
              )}

              {!issuesLoading &&
                issuesError && (
                <div className="quality-issues-error">
                  <p>
                    {issuesError}
                  </p>

                  <button
                    type="button"
                    onClick={() => {
                      if (
                        selectedRunId !== null
                      ) {
                        void loadIssues(
                          selectedRunId,
                          selectedCheck.check_name,
                        )
                      }
                    }}
                  >
                    Retry
                  </button>
                </div>
              )}

              {!issuesLoading &&
                !issuesError &&
                totalIssues === 0 && (
                <div className="quality-issues-state">
                  No findings for{' '}
                  {checkLabel(
                    selectedCheck.check_name,
                  )}
                  . This control completed
                  without persisted issues.
                </div>
              )}

              {!issuesLoading &&
                !issuesError &&
                totalIssues > 0 && (
                <>
                  <div className="quality-issues-summary">
                    <span>
                      {totalIssues.toLocaleString(
                        'de-AT',
                      )}
                      {' findings'}
                    </span>

                    <span>
                      Showing{' '}
                      {issues.length.toLocaleString(
                        'de-AT',
                      )}
                      {issues.length < totalIssues
                        ? ' of all findings'
                        : ' findings'}
                    </span>
                  </div>

                  <div className="quality-issues-list">
                    {issues.map((issue) => (
                      <article
                        key={issue.id}
                        className={
                          issue.blocking
                            ? (
                                'quality-issue-card ' +
                                'quality-issue-card-blocking'
                              )
                            : 'quality-issue-card'
                        }
                      >
                        <header className="quality-issue-header">
                          <div>
                            <div className="quality-issue-title-row">
                              <strong>
                                {issue.entity_key ??
                                  (
                                    issue.company_id !== null
                                      ? `Company #${issue.company_id}`
                                      : 'Platform'
                                  )}
                              </strong>

                              <span
                                className={
                                  (
                                    'quality-issue-severity ' +
                                    'quality-issue-severity-' +
                                    issue.severity
                                  )
                                }
                              >
                                {issue.severity}
                              </span>

                              {issue.blocking && (
                                <span className="quality-issue-blocking">
                                  Blocking
                                </span>
                              )}
                            </div>

                            <p className="quality-issue-check">
                              {checkLabel(
                                issue.check_name,
                              )}
                            </p>
                          </div>

                          <span className="quality-issue-id">
                            Issue #{issue.id}
                          </span>
                        </header>

                        <p className="quality-issue-message">
                          {issue.message}
                        </p>

                        <div className="quality-issue-metadata">
                          <span>
                            Metric:{' '}
                            {issue.metric ?? '—'}
                          </span>

                          <span>
                            Period:{' '}
                            {formatPeriod(
                              issue.period_start,
                              issue.period_end,
                            )}
                          </span>

                          <span>
                            Available:{' '}
                            {formatDateTime(
                              issue.available_at,
                            )}
                          </span>
                        </div>

                        {(
                          issue.actual_value !== null ||
                          issue.expected_value !== null ||
                          issue.context_json !== null
                        ) && (
                          <details className="quality-issue-details">
                            <summary>
                              Diagnostic details
                            </summary>

                            {issue.actual_value !== null && (
                              <div className="quality-issue-value">
                                <span>
                                  Actual value
                                </span>

                                <pre>
                                  {issue.actual_value}
                                </pre>
                              </div>
                            )}

                            {issue.expected_value !== null && (
                              <div className="quality-issue-value">
                                <span>
                                  Expected value
                                </span>

                                <pre>
                                  {issue.expected_value}
                                </pre>
                              </div>
                            )}

                            {issue.context_json !== null && (
                              <div className="quality-issue-value">
                                <span>
                                  Context
                                </span>

                                <pre>
                                  {JSON.stringify(
                                    issue.context_json,
                                    null,
                                    2,
                                  )}
                                </pre>
                              </div>
                            )}
                          </details>
                        )}
                      </article>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </section>
    </main>
  )
}

export default DataQualityPage