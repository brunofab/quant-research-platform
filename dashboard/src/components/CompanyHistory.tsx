import {
  useEffect,
  useState,
} from 'react'

import CapitalCycleCharts from './CapitalCycleCharts'
import RegimeTimeline from './RegimeTimeline'
import type {
  CapitalCycleHistoryPeriod,
} from '../types/capitalCycle'

type CompanyHistoryProps = {
  ticker: string
  classifier: string
  vintage: string
  periods: CapitalCycleHistoryPeriod[]
  loading: boolean
  error: string | null
  onClose: () => void
}

function formatValue(
  value: number | undefined,
): string {
  if (value === undefined) {
    return '—'
  }

  return value.toFixed(1)
}

function regimeClassName(
  regime: string | null,
): string {
  if (!regime) {
    return 'regime-badge regime-none'
  }

  return (
    'regime-badge regime-' +
    regime.toLowerCase()
  )
}

function CompanyHistory({
  ticker,
  classifier,
  vintage,
  periods,
  loading,
  error,
  onClose,
}: CompanyHistoryProps) {
  const [selectedPeriodIndex, setSelectedPeriodIndex] =
    useState(() =>
      periods.length > 0
        ? periods.length - 1
        : -1,
    )

  useEffect(() => {
    setSelectedPeriodIndex(
      periods.length > 0
        ? periods.length - 1
        : -1,
    )
  }, [periods])

  return (
    <section className="dashboard-card history-card">
      <div className="card-header history-header">
        <div>
          <p className="history-eyebrow">
            Company history
          </p>

          <h2>{ticker} Capital Cycle</h2>

          <p>
            {classifier.toUpperCase()} ·{' '}
            {vintage.toUpperCase()} vintage
          </p>
        </div>

        <button
          type="button"
          className="close-history-button"
          onClick={onClose}
        >
          Close
        </button>
      </div>

      {loading && (
        <div className="loading-message history-message">
          Loading {ticker} history…
        </div>
      )}

      {error && (
        <div className="error-message history-message">
          API error: {error}
        </div>
      )}

      {!loading && !error && periods.length === 0 && (
        <div className="empty-message">
          No historical periods were returned.
        </div>
      )}

      {!loading && !error && periods.length > 0 && (
        <>
          <RegimeTimeline
            periods={periods}
            selectedPeriodIndex={selectedPeriodIndex}
            onSelectPeriodIndex={
              setSelectedPeriodIndex
            }
          />

          <CapitalCycleCharts
            periods={periods}
            selectedPeriodIndex={selectedPeriodIndex}
          />

          <div className="history-table-heading">
            <div>
              <h3>Historical periods</h3>

              <p>
                Raw, confirmed and pending regime
                states.
              </p>
            </div>

            <span>
              {periods.length} quarters
            </span>
          </div>

          <div className="table-wrapper">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Fiscal period</th>
                  <th>As of</th>
                  <th>Confirmed</th>
                  <th>Raw</th>
                  <th>Candidate</th>
                  <th>Progress</th>
                  <th>Growth gap</th>
                  <th>Intensity YoY</th>
                  <th>FCF margin YoY</th>
                  <th>Gap QoQ</th>
                  <th>Intensity QoQ</th>
                  <th>FCF QoQ</th>
                </tr>
              </thead>

              <tbody>
                {periods.map((period, index) => {
                  const features =
                    period.features_percentage_points

                  const isSelected =
                    index === selectedPeriodIndex

                  return (
                    <tr
                      key={
                        `${period.fiscal_year}-` +
                        `${period.fiscal_quarter}-` +
                        `${period.as_of}`
                      }
                      className={
                        isSelected
                          ? 'selected-row'
                          : undefined
                      }
                    >
                      <td>
                        {period.fiscal_period ?? '—'}
                      </td>

                      <td>
                        {period.as_of ?? '—'}
                      </td>

                      <td>
                        <span
                          className={regimeClassName(
                            period.confirmed_regime,
                          )}
                        >
                          {period.confirmed_regime ??
                            '—'}
                        </span>
                      </td>

                      <td>
                        <span
                          className={regimeClassName(
                            period.raw_regime,
                          )}
                        >
                          {period.raw_regime ?? '—'}
                        </span>
                      </td>

                      <td>
                        {period.candidate_regime ??
                          '—'}
                      </td>

                      <td>
                        {period.confirmation_progress ??
                          '—'}
                      </td>

                      <td>
                        {formatValue(
                          features?.capex_growth_gap,
                        )}
                      </td>

                      <td>
                        {formatValue(
                          features
                            ?.capex_intensity_yoy_delta,
                        )}
                      </td>

                      <td>
                        {formatValue(
                          features
                            ?.fcf_margin_yoy_delta,
                        )}
                      </td>

                      <td>
                        {formatValue(
                          features
                            ?.capex_growth_gap_qoq_delta,
                        )}
                      </td>

                      <td>
                        {formatValue(
                          features
                            ?.capex_intensity_yoy_delta_qoq_delta,
                        )}
                      </td>

                      <td>
                        {formatValue(
                          features
                            ?.fcf_margin_yoy_delta_qoq_delta,
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}

export default CompanyHistory