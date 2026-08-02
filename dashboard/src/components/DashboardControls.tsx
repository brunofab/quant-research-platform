import type { FormEvent } from 'react'

export type Vintage = 'first' | 'latest'
export type Classifier = 'baseline' | 'calibrated'

type DashboardControlsProps = {
  tickerInput: string
  vintage: Vintage
  classifier: Classifier
  loading: boolean
  onTickerInputChange: (value: string) => void
  onVintageChange: (value: Vintage) => void
  onClassifierChange: (value: Classifier) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

function DashboardControls({
  tickerInput,
  vintage,
  classifier,
  loading,
  onTickerInputChange,
  onVintageChange,
  onClassifierChange,
  onSubmit,
}: DashboardControlsProps) {
  return (
    <form
      className="dashboard-controls"
      onSubmit={onSubmit}
    >
      <label className="control-field control-tickers">
        <span>Companies</span>

        <input
          type="text"
          value={tickerInput}
          placeholder="GOOGL, MSFT, META, AMZN"
          onChange={(event) => {
            onTickerInputChange(event.target.value)
          }}
        />
      </label>

      <label className="control-field">
        <span>Vintage</span>

        <select
          value={vintage}
          onChange={(event) => {
            onVintageChange(
              event.target.value as Vintage,
            )
          }}
        >
          <option value="latest">Latest</option>
          <option value="first">First</option>
        </select>
      </label>

      <label className="control-field">
        <span>Classifier</span>

        <select
          value={classifier}
          onChange={(event) => {
            onClassifierChange(
              event.target.value as Classifier,
            )
          }}
        >
          <option value="baseline">
            Baseline
          </option>

          <option value="calibrated">
            Calibrated
          </option>
        </select>
      </label>

      <button
        type="submit"
        disabled={loading}
      >
        {loading ? 'Loading…' : 'Apply'}
      </button>
    </form>
  )
}

export default DashboardControls
