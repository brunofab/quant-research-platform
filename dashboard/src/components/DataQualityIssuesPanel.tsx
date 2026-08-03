import {
  useEffect,
  useState,
} from 'react'

import type {
  DataQualityIssue,
  DataQualityIssuesResponse,
} from '../types/pipeline'

type DataQualityIssuesPanelProps = {
  runId: number
  totalIssues: number
}

function formatPeriod(
  issue: DataQualityIssue,
): string {
  if (!issue.period_start && !issue.period_end) {
    return 'No fiscal period'
  }

  if (!issue.period_start) {
    return issue.period_end ?? '—'
  }

  if (!issue.period_end) {
    return issue.period_start
  }

  return (
    `${issue.period_start} – ` +
    issue.period_end
  )
}

function issueSeverityClassName(
  issue: DataQualityIssue,
): string {
  return (
    'quality-issue-severity ' +
    `quality-issue-severity-${issue.severity}`
  )
}

function DataQualityIssuesPanel({
  runId,
  totalIssues,
}: DataQualityIssuesPanelProps) {
  const [
    expanded,
    setExpanded,
  ] = useState(false)

  const [
    loading,
    setLoading,
  ] = useState(false)

  const [
    error,
    setError,
  ] = useState<string | null>(null)

  const [
    response,
    setResponse,
  ] = useState<
    DataQualityIssuesResponse | null
  >(null)

  useEffect(() => {
    setExpanded(false)
    setLoading(false)
    setError(null)
    setResponse(null)
  }, [runId])

  async function loadIssues(): Promise<void> {
    setLoading(true)
    setError(null)

    try {
      const apiResponse = await fetch(
        `/api/v1/data-quality/runs/${runId}` +
        '/issues?limit=50',
      )

      if (!apiResponse.ok) {
        throw new Error(
          'Data-quality issues could not be loaded.',
        )
      }

      const payload =
        await apiResponse.json() as
          DataQualityIssuesResponse

      setResponse(payload)
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : (
              'An unknown error occurred while ' +
              'loading data-quality issues.'
            )

      setError(message)
    } finally {
      setLoading(false)
    }
  }

  async function togglePanel(): Promise<void> {
    const shouldExpand = !expanded

    setExpanded(shouldExpand)

    if (
      shouldExpand &&
      response === null &&
      !loading
    ) {
      await loadIssues()
    }
  }

  return (
    <div className="quality-issues-panel">
      <button
        className="quality-issues-toggle"
        type="button"
        aria-expanded={expanded}
        onClick={() => {
          void togglePanel()
        }}
      >
        <span>
          {expanded
            ? 'Hide quality issues'
            : 'Show quality issues'}
        </span>

        <span className="quality-issues-count">
          {totalIssues.toLocaleString('de-AT')}
        </span>
      </button>

      {expanded && (
        <div className="quality-issues-content">
          {loading && (
            <div className="quality-issues-state">
              <span className="pipeline-status-spinner" />

              Loading quality issues…
            </div>
          )}

          {error && !loading && (
            <div className="quality-issues-error">
              <p>{error}</p>

              <button
                type="button"
                onClick={() => {
                  void loadIssues()
                }}
              >
                Try again
              </button>
            </div>
          )}

          {response &&
            !loading &&
            !error && (
              <>
                <div className="quality-issues-summary">
                  <span>
                    Showing{' '}
                    {response.returned_issues
                      .toLocaleString('de-AT')}
                    {' '}of{' '}
                    {response.total_issues
                      .toLocaleString('de-AT')}
                    {' '}issues
                  </span>

                  {response.total_issues >
                    response.returned_issues && (
                      <span>
                        First 50 results
                      </span>
                    )}
                </div>

                {response.issues.length === 0 ? (
                  <div className="quality-issues-state">
                    No issues were found for this run.
                  </div>
                ) : (
                  <div className="quality-issues-list">
                    {response.issues.map(
                      issue => (
                        <article
                          className={
                            'quality-issue-card ' +
                            (
                              issue.blocking
                                ? (
                                    'quality-issue-card-' +
                                    'blocking'
                                  )
                                : ''
                            )
                          }
                          key={issue.id}
                        >
                          <div className="quality-issue-header">
                            <div>
                              <div className="quality-issue-title-row">
                                <strong>
                                  {issue.entity_key}
                                </strong>

                                <span
                                  className={
                                    issueSeverityClassName(
                                      issue,
                                    )
                                  }
                                >
                                  {issue.severity}
                                </span>

                                {issue.blocking && (
                                  <span className="quality-issue-blocking">
                                    blocking
                                  </span>
                                )}
                              </div>

                              <p className="quality-issue-check">
                                {issue.check_name}
                                {issue.metric
                                  ? ` · ${issue.metric}`
                                  : ''}
                              </p>
                            </div>

                            <span className="quality-issue-id">
                              Issue #{issue.id}
                            </span>
                          </div>

                          <p className="quality-issue-message">
                            {issue.message}
                          </p>

                          <div className="quality-issue-metadata">
                            <span>
                              Period:{' '}
                              {formatPeriod(issue)}
                            </span>

                            <span>
                              Dataset: {issue.dataset}
                            </span>
                          </div>

                          {(
                            issue.actual_value ||
                            issue.expected_value ||
                            issue.context_json
                          ) && (
                            <details className="quality-issue-details">
                              <summary>
                                Show diagnostic context
                              </summary>

                              {issue.actual_value && (
                                <div className="quality-issue-value">
                                  <span>Actual</span>

                                  <pre>
                                    {issue.actual_value}
                                  </pre>
                                </div>
                              )}

                              {issue.expected_value && (
                                <div className="quality-issue-value">
                                  <span>Expected</span>

                                  <pre>
                                    {issue.expected_value}
                                  </pre>
                                </div>
                              )}

                              {issue.context_json && (
                                <div className="quality-issue-value">
                                  <span>Context</span>

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
                      ),
                    )}
                  </div>
                )}
              </>
            )}
        </div>
      )}
    </div>
  )
}

export default DataQualityIssuesPanel
