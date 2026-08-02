import {
  useEffect,
  useState,
} from 'react'

import QuarterDiagnosisPanel from './QuarterDiagnosisPanel'
import type {
  CapitalCycleHistoryPeriod,
} from '../types/capitalCycle'

type RegimeTimelineProps = {
  periods: CapitalCycleHistoryPeriod[]
}

function periodKey(
  period: CapitalCycleHistoryPeriod,
): string {
  return (
    `${period.fiscal_year}-` +
    `${period.fiscal_quarter}-` +
    `${period.as_of ?? 'unknown'}`
  )
}

function regimeClassName(
  regime: string | null,
): string {
  if (!regime) {
    return 'timeline-period timeline-none'
  }

  return (
    'timeline-period timeline-' +
    regime.toLowerCase()
  )
}

function RegimeTimeline({
  periods,
}: RegimeTimelineProps) {
  const [selectedPeriodKey, setSelectedPeriodKey] =
    useState<string | null>(() => {
      const latestPeriod =
        periods[periods.length - 1]

      return latestPeriod
        ? periodKey(latestPeriod)
        : null
    })

  useEffect(() => {
    const latestPeriod =
      periods[periods.length - 1]

    setSelectedPeriodKey(
      latestPeriod
        ? periodKey(latestPeriod)
        : null,
    )
  }, [periods])

  const selectedPeriod =
    periods.find(
      (period) =>
        periodKey(period) === selectedPeriodKey,
    ) ??
    periods[periods.length - 1] ??
    null

  return (
    <section className="regime-timeline-section">
      <div className="timeline-heading">
        <div>
          <h3>Confirmed regime timeline</h3>

          <p>
            Select a fiscal quarter to inspect its
            regime decision and feature values.
          </p>
        </div>

        <div className="timeline-legend">
          <span>
            <i className="legend-raw-difference" />
            Raw differs
          </span>

          <span>
            <i className="legend-candidate" />
            Candidate pending
          </span>
        </div>
      </div>

      <div className="regime-timeline">
        {periods.map((period) => {
          const key = periodKey(period)

          const rawDiffers =
            period.raw_regime !==
            period.confirmed_regime

          const candidatePending =
            period.confirmation_pending &&
            period.candidate_regime !== null

          const changed =
            period.changed_this_period

          const isSelected =
            key === periodKey(selectedPeriod)

          return (
            <button
              key={key}
              type="button"
              className={
                `${regimeClassName(
                  period.confirmed_regime,
                )}` +
                `${
                  changed
                    ? ' timeline-changed'
                    : ''
                }` +
                `${
                  isSelected
                    ? ' timeline-selected'
                    : ''
                }`
              }
              title={[
                period.fiscal_period ??
                  'Unknown period',
                `Available: ${period.as_of ?? '—'}`,
                `Confirmed: ${
                  period.confirmed_regime ?? '—'
                }`,
                `Raw: ${period.raw_regime ?? '—'}`,
                candidatePending
                  ? `Candidate: ${
                      period.candidate_regime ?? '—'
                    }`
                  : null,
                candidatePending
                  ? `Progress: ${
                      period.confirmation_progress ??
                      '—'
                    }`
                  : null,
              ]
                .filter(Boolean)
                .join('\n')}
              aria-pressed={isSelected}
              onClick={() => {
                setSelectedPeriodKey(key)
              }}
            >
              <span className="timeline-period-label">
                {period.fiscal_period ?? '—'}
              </span>

              <span className="timeline-regime-label">
                {period.confirmed_regime ?? '—'}
              </span>

              <span className="timeline-markers">
                {rawDiffers && (
                  <span
                    className="timeline-raw-marker"
                    aria-label="Raw regime differs"
                  />
                )}

                {candidatePending && (
                  <span
                    className="timeline-candidate-marker"
                    aria-label="Candidate regime pending"
                  />
                )}
              </span>
            </button>
          )
        })}
      </div>

      {selectedPeriod && (
        <QuarterDiagnosisPanel
          period={selectedPeriod}
        />
      )}
    </section>
  )
}

export default RegimeTimeline