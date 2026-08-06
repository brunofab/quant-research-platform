import {
  useCallback,
  useEffect,
  useState,
} from 'react'
import { Link } from 'react-router-dom'

import PipelineStatusCard from '../components/PipelineStatusCard'
import type {
  DataQualityCheckSummary,
  DataQualityChecksResponse,
  PipelineStatusResponse,
} from '../types/pipeline'

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

function checkStatusClassName(
  status: DataQualityCheckSummary['status'],
): string {
  return (
    'home-quality-status ' +
    `home-quality-status-${status}`
  )
}

function HomePage() {
  const [
    pipelineStatus,
    setPipelineStatus,
  ] = useState<PipelineStatusResponse | null>(
    null,
  )

  const [
    pipelineLoading,
    setPipelineLoading,
  ] = useState(true)

  const [
    pipelineError,
    setPipelineError,
  ] = useState<string | null>(null)

  const [
    qualityChecks,
    setQualityChecks,
  ] = useState<DataQualityCheckSummary[]>([])

  const [
    qualityChecksLoading,
    setQualityChecksLoading,
  ] = useState(false)

  const [
    qualityChecksError,
    setQualityChecksError,
  ] = useState<string | null>(null)

  const loadQualityChecks = useCallback(
    async (
      qualityRunId: number,
    ): Promise<void> => {
      setQualityChecksLoading(true)
      setQualityChecksError(null)

      try {
        const response = await fetch(
          (
            '/api/v1/data-quality/runs/' +
            `${qualityRunId}/checks`
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

        setQualityChecks(payload.checks)
      } catch (error) {
        setQualityChecks([])

        setQualityChecksError(
          error instanceof Error
            ? error.message
            : 'Unable to load quality checks.',
        )
      } finally {
        setQualityChecksLoading(false)
      }
    },
    [],
  )

  const loadPlatformStatus = useCallback(
    async (): Promise<void> => {
      setPipelineLoading(true)
      setPipelineError(null)

      try {
        const response = await fetch(
          '/api/v1/pipeline/status',
        )

        if (!response.ok) {
          throw new Error(
            (
              'Pipeline API returned ' +
              `HTTP ${response.status}`
            ),
          )
        }

        const payload =
          await response.json() as
            PipelineStatusResponse

        setPipelineStatus(payload)

        if (payload.data_quality) {
          await loadQualityChecks(
            payload.data_quality.id,
          )
        } else {
          setQualityChecks([])
        }
      } catch (error) {
        setPipelineStatus(null)
        setQualityChecks([])

        setPipelineError(
          error instanceof Error
            ? error.message
            : 'Unable to load platform status.',
        )
      } finally {
        setPipelineLoading(false)
      }
    },
    [loadQualityChecks],
  )

  useEffect(() => {
    void loadPlatformStatus()
  }, [loadPlatformStatus])

  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">
            Quant Research Platform
          </p>

          <h1>
            Research Overview
          </h1>

          <p className="subtitle">
            Platform health, data-quality
            controls and active investment
            research projects.
          </p>
        </div>

        <button
          className="apply-button"
          type="button"
          disabled={
            pipelineLoading ||
            qualityChecksLoading
          }
          onClick={() => {
            void loadPlatformStatus()
          }}
        >
          Refresh status
        </button>
      </header>

      <PipelineStatusCard
        data={pipelineStatus}
        loading={pipelineLoading}
        error={pipelineError}
      />

      <section className="dashboard-card home-quality-card">
        <div className="card-header">
          <div>
            <p className="eyebrow">
              Data controls
            </p>

            <h2>
              Latest quality checks
            </h2>

            <p>
              Aggregated results from the most
              recent linked data-quality run.
            </p>
          </div>

          <span className="company-count">
            {qualityChecks.length > 0
              ? `${qualityChecks.length} checks`
              : 'No results'}
          </span>
        </div>

        {qualityChecksLoading && (
          <div className="home-placeholder">
            Loading quality-check results…
          </div>
        )}

        {!qualityChecksLoading &&
          qualityChecksError && (
            <div className="home-quality-error">
              {qualityChecksError}
            </div>
          )}

        {!qualityChecksLoading &&
          !qualityChecksError &&
          qualityChecks.length === 0 && (
            <div className="home-placeholder">
              No persisted quality-check
              results are available for the
              latest pipeline run.
            </div>
          )}

        {!qualityChecksLoading &&
          !qualityChecksError &&
          qualityChecks.length > 0 && (
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
                    <th>Duration</th>
                  </tr>
                </thead>

                <tbody>
                  {qualityChecks.map((check) => (
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
                            checkStatusClassName(
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

        <div className="home-quality-footer">
          <Link
            className="home-project-link"
            to="/data-quality"
          >
            Open data-quality view
          </Link>
        </div>
      </section>

      <section className="home-projects">
        <div className="home-section-heading">
          <div>
            <p className="eyebrow">
              Investment theses
            </p>

            <h2>
              Research projects
            </h2>
          </div>
        </div>

        <div className="home-project-grid">
          <article className="home-project-card">
            <div>
              <span className="home-project-status">
                Active
              </span>

              <h3>
                AI Capital Cycle
              </h3>

              <p>
                CAPEX acceleration, cash-flow
                pressure, transition signals
                and eventual normalization.
              </p>
            </div>

            <Link
              className="home-project-link"
              to="/theses/capital-cycle"
            >
              Open thesis
            </Link>
          </article>

          <article className="home-project-card home-project-card-planned">
            <div>
              <span className="home-project-status">
                Planned
              </span>

              <h3>
                Nike Turnaround
              </h3>

              <p>
                Revenue stabilization,
                inventory, margins and brand
                recovery.
              </p>
            </div>

            <span className="home-project-link-disabled">
              Not configured
            </span>
          </article>

          <article className="home-project-card home-project-card-planned">
            <div>
              <span className="home-project-status">
                Planned
              </span>

              <h3>
                Memory Cycle
              </h3>

              <p>
                Pricing, inventories, supply,
                CAPEX and semiconductor-cycle
                conditions.
              </p>
            </div>

            <span className="home-project-link-disabled">
              Not configured
            </span>
          </article>
        </div>
      </section>
    </main>
  )
}

export default HomePage