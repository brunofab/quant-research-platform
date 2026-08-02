import {
  useEffect,
  useState,
} from 'react'
import type { FormEvent } from 'react'

import CompanyHistory from './components/CompanyHistory'
import DashboardControls from './components/DashboardControls'
import type {
  Classifier,
  Vintage,
} from './components/DashboardControls'
import PipelineStatusCard from './components/PipelineStatusCard'
import UniverseTable from './components/UniverseTable'
import type {
  CapitalCycleHistoryPayload,
  CapitalCyclePayload,
} from './types/capitalCycle'
import type {
  PipelineStatusResponse,
} from './types/pipeline'

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
    .map((ticker) =>
      ticker.trim().toUpperCase(),
    )
    .filter(Boolean)
    .join(',')
}

function App() {
  const [data, setData] =
    useState<CapitalCyclePayload | null>(null)

  const [error, setError] =
    useState<string | null>(null)

  const [loading, setLoading] =
    useState(false)

  const [tickerInput, setTickerInput] =
    useState(DEFAULT_FILTERS.tickers)

  const [vintage, setVintage] =
    useState<Vintage>(
      DEFAULT_FILTERS.vintage,
    )

  const [classifier, setClassifier] =
    useState<Classifier>(
      DEFAULT_FILTERS.classifier,
    )

  const [
    appliedFilters,
    setAppliedFilters,
  ] = useState<DashboardFilters>(
    DEFAULT_FILTERS,
  )

  const [refreshKey, setRefreshKey] =
    useState(0)

  const [
    selectedTicker,
    setSelectedTicker,
  ] = useState<string | null>(null)

  const [historyData, setHistoryData] =
    useState<CapitalCycleHistoryPayload | null>(
      null,
    )

  const [
    historyLoading,
    setHistoryLoading,
  ] = useState(false)

  const [historyError, setHistoryError] =
    useState<string | null>(null)

  const [
    pipelineStatus,
    setPipelineStatus,
  ] = useState<PipelineStatusResponse | null>(
    null,
  )

  const [
    pipelineStatusLoading,
    setPipelineStatusLoading,
  ] = useState(true)

  const [
    pipelineStatusError,
    setPipelineStatusError,
  ] = useState<string | null>(null)

  useEffect(() => {
    const controller =
      new AbortController()

    const loadOverview = async () => {
      setLoading(true)
      setError(null)

      try {
        const parameters =
          new URLSearchParams({
            vintage:
              appliedFilters.vintage,
            classifier:
              appliedFilters.classifier,
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
            signal: controller.signal,
          },
        )

        if (!response.ok) {
          throw new Error(
            `API returned HTTP ${response.status}`,
          )
        }

        const payload =
          (await response.json()) as CapitalCyclePayload

        setData(payload)
      } catch (unknownError) {
        if (
          unknownError instanceof
            DOMException &&
          unknownError.name ===
            'AbortError'
        ) {
          return
        }

        setError(
          unknownError instanceof Error
            ? unknownError.message
            : 'Unknown API error',
        )
      } finally {
        if (
          !controller.signal.aborted
        ) {
          setLoading(false)
        }
      }
    }

    void loadOverview()

    return () => {
      controller.abort()
    }
  }, [appliedFilters, refreshKey])

  useEffect(() => {
    if (!selectedTicker) {
      setHistoryData(null)
      setHistoryError(null)
      setHistoryLoading(false)
      return
    }

    const controller =
      new AbortController()

    const loadHistory = async () => {
      setHistoryLoading(true)
      setHistoryError(null)

      try {
        const parameters =
          new URLSearchParams({
            vintage:
              appliedFilters.vintage,
            classifier:
              appliedFilters.classifier,
            confirmation_hits: '2',
            confirmation_window: '3',
            limit: '24',
          })

        const response = await fetch(
          `/api/v1/capital-cycle/history/` +
            `${encodeURIComponent(
              selectedTicker,
            )}` +
            `?${parameters}`,
          {
            signal: controller.signal,
          },
        )

        if (!response.ok) {
          let detail = ''

          try {
            const payload =
              (await response.json()) as {
                detail?: string
              }

            detail = payload.detail
              ? `: ${payload.detail}`
              : ''
          } catch {
            detail = ''
          }

          throw new Error(
            `API returned HTTP ` +
              `${response.status}` +
              `${detail}`,
          )
        }

        const payload =
          (await response.json()) as CapitalCycleHistoryPayload

        setHistoryData(payload)
      } catch (unknownError) {
        if (
          unknownError instanceof
            DOMException &&
          unknownError.name ===
            'AbortError'
        ) {
          return
        }

        setHistoryError(
          unknownError instanceof Error
            ? unknownError.message
            : 'Unknown history API error',
        )
      } finally {
        if (
          !controller.signal.aborted
        ) {
          setHistoryLoading(false)
        }
      }
    }

    void loadHistory()

    return () => {
      controller.abort()
    }
  }, [
    selectedTicker,
    appliedFilters,
    refreshKey,
  ])

  useEffect(() => {
    const controller =
      new AbortController()

    const loadPipelineStatus =
      async () => {
        setPipelineStatusLoading(true)
        setPipelineStatusError(null)

        try {
          const response = await fetch(
            '/api/v1/pipeline/status',
            {
              signal: controller.signal,
            },
          )

          if (!response.ok) {
            throw new Error(
              `Request failed with status ` +
                `${response.status}.`,
            )
          }

          const responseData =
            (await response.json()) as PipelineStatusResponse

          setPipelineStatus(
            responseData,
          )
        } catch (requestError) {
          if (
            controller.signal.aborted
          ) {
            return
          }

          const message =
            requestError instanceof Error
              ? requestError.message
              : 'Unknown pipeline status error.'

          setPipelineStatusError(
            message,
          )
        } finally {
          if (
            !controller.signal.aborted
          ) {
            setPipelineStatusLoading(
              false,
            )
          }
        }
      }

    void loadPipelineStatus()

    return () => {
      controller.abort()
    }
  }, [])

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
      setTickerInput(
        nextFilters.tickers,
      )
      setAppliedFilters(nextFilters)
      setSelectedTicker(null)
      setHistoryData(null)
      return
    }

    setRefreshKey(
      (current) => current + 1,
    )
  }

  const classifierResult =
    data?.classifiers[0]

  const historyClassifier =
    historyData?.classifiers[0]

  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">
            Quant Research Platform
          </p>

          <h1>
            Capital-Cycle Overview
          </h1>

          <p className="subtitle">
            Point-in-time investment and
            cash-flow pressure across the
            current universe.
          </p>
        </div>

        {data && (
          <div className="metadata">
            <span>
              Vintage:{' '}
              {data.snapshot_vintage}
            </span>

            <span>
              Confirmation:{' '}
              {
                data.confirmation
                  .required_hits
              }{' '}
              of{' '}
              {
                data.confirmation
                  .window_quarters
              }
            </span>
          </div>
        )}
      </header>

      <DashboardControls
        tickerInput={tickerInput}
        vintage={vintage}
        classifier={classifier}
        loading={loading}
        onTickerInputChange={
          setTickerInput
        }
        onVintageChange={setVintage}
        onClassifierChange={
          setClassifier
        }
        onSubmit={handleSubmit}
      />

      <PipelineStatusCard
        data={pipelineStatus}
        loading={pipelineStatusLoading}
        error={pipelineStatusError}
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
              <h2>
                Universe snapshot
              </h2>

              <p>
                Classifier:{' '}
                {classifierResult.classifier.toUpperCase()}
              </p>
            </div>

            <span className="company-count">
              {
                classifierResult
                  .companies.length
              }{' '}
              companies
            </span>
          </div>

          {classifierResult.companies
            .length > 0 ? (
            <UniverseTable
              companies={
                classifierResult.companies
              }
              selectedTicker={
                selectedTicker
              }
              onSelectTicker={
                setSelectedTicker
              }
            />
          ) : (
            <div className="empty-message">
              No companies with complete
              signal data were returned.
            </div>
          )}
        </section>
      )}

      {selectedTicker && (
        <CompanyHistory
          ticker={selectedTicker}
          classifier={
            historyClassifier
              ?.classifier ??
            appliedFilters.classifier
          }
          vintage={
            historyData
              ?.snapshot_vintage ??
            appliedFilters.vintage
          }
          periods={
            historyClassifier?.periods ??
            []
          }
          loading={historyLoading}
          error={historyError}
          onClose={() => {
            setSelectedTicker(null)
          }}
        />
      )}
    </main>
  )
}

export default App