export type CapitalCycleFeatures = {
  capex_growth_gap: number
  capex_intensity_yoy_delta: number
  fcf_margin_yoy_delta: number
  capex_growth_gap_qoq_delta: number
  capex_intensity_yoy_delta_qoq_delta: number
  fcf_margin_yoy_delta_qoq_delta: number
}

export type CapitalCycleCompany = {
  ticker: string
  status: string
  fiscal_period: string | null
  fiscal_year: number | null
  fiscal_quarter: number | null
  as_of: string | null
  confirmed_regime: string | null
  raw_regime: string | null
  candidate_regime: string | null
  candidate_hits: number
  confirmation_required: number
  confirmation_pending: boolean
  confirmation_progress: string | null
  changed_this_period: boolean
  features_percentage_points: CapitalCycleFeatures | null
}

export type CapitalCycleClassifier = {
  classifier: string
  companies: CapitalCycleCompany[]
}

export type CapitalCyclePayload = {
  schema_version: number
  requested_as_of: string | null
  snapshot_vintage: string
  units: {
    features: string
  }
  confirmation: {
    required_hits: number
    window_quarters: number
  }
  classifiers: CapitalCycleClassifier[]
}

export type CapitalCycleHistoryPeriod = Omit<
  CapitalCycleCompany,
  'ticker' | 'status'
>

export type CapitalCycleHistoryPayload = {
  schema_version: number
  ticker: string
  requested_as_of: string | null
  snapshot_vintage: string
  units: {
    features: string
  }
  confirmation: {
    required_hits: number
    window_quarters: number
  }
  classifiers: Array<{
    classifier: string
    periods: CapitalCycleHistoryPeriod[]
  }>
}