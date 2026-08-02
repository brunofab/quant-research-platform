import {
  useCallback,
  useEffect,
  useState,
} from 'react'
import type { FormEvent } from 'react'

import DashboardControls from './components/DashboardControls'
import type {
  Classifier,
  Vintage,
} from './components/DashboardControls'
import UniverseTable from './components/UniverseTable'
import type {
  CapitalCyclePayload,
} from './types/capitalCycle'

type DashboardFilters = {
  tickers: string
  vintage: Vintage
  classifier: Classifier
}

const DEFAULT_FILTERS: DashboardFilters = {
  tickers: 'GOOGL,MSFT,META,AMZN',
  vintage: 'latest',
  classifier: 'baseline',
}

function normalizeTickerInput(
  value: string,
): string {
  return value
    .split(',')
    .map((ticker) => ticker.trim().toUpperCase())
    .filter(Boolean)
    .join(',')
}

function App() {
  const [data, setData] =
    useState<CapitalCyclePayload | null>(null)

  const [error, setError] =
    useState<string | null>(null)

  const [loading, setLoading] = useState(false)

  const [tickerInput, setTickerInput] = useState(
    DEFAULT_FILTERS.tickers,
  )

  const [vintage, setVintage] =
    useState<Vintage>(DEFAULT_FILTERS.vintage)

  const [classifier, setClassifier] =
    useState<Classifier>(
      DEFAULT_FILTERS.classifier,
    )

  const [appliedFilters, setAppliedFilters] =
    useState<DashboardFilters>(DEFAULT_FILTERS)

  const [refreshKey, setRefreshKey] = useState(0)

  const loadOverview = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true)
      setError(null)

      try {
        const parameters = new URLSearchParams({
          vintage: appliedFilters.vintage,
          classifier: appliedFilters.classifier,
          confirmation_hits: '2',
          confirmation_window: '3',
        })

        const normalizedTickers =
          normalizeTickerInput(
            appliedFilters.tickers,
          )

        if (normalizedTickers) {
          parameters.set(
            'tickers',
            normalizedTickers,
          )
        }

        const response = await fetch(
          `/api/v1/capital-cycle/overview?${parameters}`,
          {
            signal,
          },
        )

        if (!response.ok) {
          let detail = ''

          try {
            const errorPayload =
              (await response.json()) as {
                detail?: string
              }

            detail = errorPayload.detail
              ? `: ${errorPayload.detail}`
              : ''
          } catch {
            detail = ''
          }

          throw new Error(
            `API returned HTTP ${response.status}${detail}`,
          )
        }

        const payload =
          (await response.json()) as CapitalCyclePayload

        setData(payload)
      } catch (unknownError) {
        if (
          unknownError instanceof DOMException &&
          unknownError.name === 'AbortError'
        ) {
          return
        }

        setError(
          unknownError instanceof Error
            ? unknownError.message
            : 'Unknown API error',
        )
      } finally {
        if (!signal.aborted) {
          setLoading(false)
        }
      }
    },
    [appliedFilters, refreshKey],
  )

  useEffect(() => {
    const controller = new AbortController()

    void loadOverview(controller.signal)

    return () => {
      controller.abort()
    }
  }, [loadOverview])

  const handleSubmit = (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()

    const nextFilters: DashboardFilters = {
      tickers: normalizeTickerInput(
        tickerInput,
      ),
      vintage,
      classifier,
    }

    const filtersChanged =
      nextFilters.tickers !==
        appliedFilters.tickers ||
      nextFilters.vintage !==
        appliedFilters.vintage ||
      nextFilters.classifier !==
        appliedFilters.classifier

    if (filtersChanged) {
      setTickerInput(nextFilters.tickers)
      setAppliedFilters(nextFilters)
      return
    }

    setRefreshKey((current) => current + 1)
  }

  const classifierResult =
    data?.classifiers[0]

  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">
            Quant Research Platform
          </p>

          <h1>Capital-Cycle Overview</h1>

          <p className="subtitle">
            Point-in-time investment and cash-flow
            pressure across the current universe.
          </p>
        </div>

        {data && (
          <div className="metadata">
            <span>
              Vintage: {data.snapshot_vintage}
            </span>

            <span>
              Confirmation:{' '}
              {data.confirmation.required_hits} of{' '}
              {data.confirmation.window_quarters}
            </span>
          </div>
        )}
      </header>

      <DashboardControls
        tickerInput={tickerInput}
        vintage={vintage}
        classifier={classifier}
        loading={loading}
        onTickerInputChange={setTickerInput}
        onVintageChange={setVintage}
        onClassifierChange={setClassifier}
        onSubmit={handleSubmit}
      />

      {error && (
        <div className="error-message">
          API error: {error}
        </div>
      )}

      {!data && loading && (
        <div className="loading-message">
          Loading capital-cycle data…
        </div>
      )}

      {classifierResult && (
        <section
          className={
            loading
              ? 'dashboard-card dashboard-card-loading'
              : 'dashboard-card'
          }
        >
          <div className="card-header">
            <div>
              <h2>Universe snapshot</h2>

              <p>
                Classifier:{' '}
                {classifierResult.classifier.toUpperCase()}
              </p>
            </div>

            <span className="company-count">
              {classifierResult.companies.length}{' '}
              companies
            </span>
          </div>

          {classifierResult.companies.length >
          0 ? (
            <UniverseTable
              companies={
                classifierResult.companies
              }
            />
          ) : (
            <div className="empty-message">
              No companies with complete signal
              data were returned.
            </div>
          )}
        </section>
      )}
    </main>
  )
}

export default App