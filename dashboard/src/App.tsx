import { useEffect, useState } from 'react'

import UniverseTable from './components/UniverseTable'
import type {
  CapitalCyclePayload,
} from './types/capitalCycle'

function App() {
  const [data, setData] =
    useState<CapitalCyclePayload | null>(null)

  const [error, setError] =
    useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    const loadOverview = async () => {
      try {
        const parameters = new URLSearchParams({
          tickers: 'GOOGL,MSFT,META,AMZN',
          vintage: 'latest',
          classifier: 'baseline',
          confirmation_hits: '2',
          confirmation_window: '3',
        })

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
      }
    }

    void loadOverview()

    return () => {
      controller.abort()
    }
  }, [])

  const classifier = data?.classifiers[0]

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

      {error && (
        <div className="error-message">
          API error: {error}
        </div>
      )}

      {!data && !error && (
        <div className="loading-message">
          Loading capital-cycle data…
        </div>
      )}

      {classifier && (
        <section className="dashboard-card">
          <div className="card-header">
            <div>
              <h2>Universe snapshot</h2>
              <p>
                Classifier:{' '}
                {classifier.classifier.toUpperCase()}
              </p>
            </div>

            <span className="company-count">
              {classifier.companies.length} companies
            </span>
          </div>

          <UniverseTable
            companies={classifier.companies}
          />
        </section>
      )}
    </main>
  )
}

export default App