import type {
  CapitalCycleHistoryPeriod,
} from '../types/capitalCycle'

type QuarterDiagnosisPanelProps = {
  period: CapitalCycleHistoryPeriod
}

type MetricItem = {
  label: string
  value: number | undefined
}

function formatValue(
  value: number | undefined,
): string {
  if (value === undefined) {
    return '—'
  }

  return `${value.toFixed(1)} pp`
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

function MetricGroup({
  title,
  description,
  metrics,
}: {
  title: string
  description: string
  metrics: MetricItem[]
}) {
  return (
    <section className="diagnosis-metric-group">
      <div className="diagnosis-metric-heading">
        <h4>{title}</h4>
        <p>{description}</p>
      </div>

      <div className="diagnosis-metric-grid">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="diagnosis-metric"
          >
            <span>{metric.label}</span>

            <strong>
              {formatValue(metric.value)}
            </strong>
          </div>
        ))}
      </div>
    </section>
  )
}

function QuarterDiagnosisPanel({
  period,
}: QuarterDiagnosisPanelProps) {
  const features =
    period.features_percentage_points

  const rawDiffers =
    period.raw_regime !==
    period.confirmed_regime

  const candidatePending =
    period.confirmation_pending &&
    period.candidate_regime !== null

  const structuralMetrics: MetricItem[] = [
    {
      label: 'Growth gap',
      value: features?.capex_growth_gap,
    },
    {
      label: 'CAPEX intensity YoY',
      value:
        features?.capex_intensity_yoy_delta,
    },
    {
      label: 'FCF margin YoY',
      value: features?.fcf_margin_yoy_delta,
    },
  ]

  const momentumMetrics: MetricItem[] = [
    {
      label: 'Growth-gap QoQ',
      value:
        features?.capex_growth_gap_qoq_delta,
    },
    {
      label: 'Intensity QoQ',
      value:
        features
          ?.capex_intensity_yoy_delta_qoq_delta,
    },
    {
      label: 'FCF QoQ',
      value:
        features
          ?.fcf_margin_yoy_delta_qoq_delta,
    },
  ]

  return (
    <section className="quarter-diagnosis-panel">
      <header className="diagnosis-header">
        <div>
          <p className="diagnosis-eyebrow">
            Selected quarter
          </p>

          <h3>
            {period.fiscal_period ?? 'Unknown period'}
          </h3>

          <p className="diagnosis-date">
            Available as of {period.as_of ?? '—'}
          </p>
        </div>

        {period.changed_this_period && (
          <span className="diagnosis-change-badge">
            Confirmed regime changed
          </span>
        )}
      </header>

      <div className="diagnosis-regime-grid">
        <div className="diagnosis-regime-card">
          <span className="diagnosis-label">
            Confirmed
          </span>

          <span
            className={regimeClassName(
              period.confirmed_regime,
            )}
          >
            {period.confirmed_regime ?? '—'}
          </span>
        </div>

        <div className="diagnosis-regime-card">
          <span className="diagnosis-label">
            Raw
          </span>

          <span
            className={regimeClassName(
              period.raw_regime,
            )}
          >
            {period.raw_regime ?? '—'}
          </span>

          {rawDiffers && (
            <small>Differs from confirmed</small>
          )}
        </div>

        <div className="diagnosis-regime-card">
          <span className="diagnosis-label">
            Candidate
          </span>

          {candidatePending ? (
            <>
              <span
                className={regimeClassName(
                  period.candidate_regime,
                )}
              >
                {period.candidate_regime}
              </span>

              <small>
                Confirmation progress:{' '}
                {period.confirmation_progress ?? '—'}
              </small>
            </>
          ) : (
            <>
              <strong className="diagnosis-no-candidate">
                No pending candidate
              </strong>

              <small>
                Current confirmed regime remains
                active
              </small>
            </>
          )}
        </div>
      </div>

      <div className="diagnosis-feature-groups">
        <MetricGroup
          title="Structural pressure"
          description="Year-over-year capital-cycle features."
          metrics={structuralMetrics}
        />

        <MetricGroup
          title="Quarterly momentum"
          description="Change from the preceding fiscal quarter."
          metrics={momentumMetrics}
        />
      </div>
    </section>
  )
}

export default QuarterDiagnosisPanel
