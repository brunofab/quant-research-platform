import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type {
  CapitalCycleHistoryPeriod,
} from '../types/capitalCycle'

type CapitalCycleChartsProps = {
  periods: CapitalCycleHistoryPeriod[]
}

type ChartPoint = {
  fiscalPeriod: string
  asOf: string | null
  growthGap: number | null
  intensityYoY: number | null
  fcfMarginYoY: number | null
  growthGapQoQ: number | null
  intensityQoQ: number | null
  fcfQoQ: number | null
}

function numberOrNull(
  value: number | undefined,
): number | null {
  return value ?? null
}

function CapitalCycleCharts({
  periods,
}: CapitalCycleChartsProps) {
  const chartData: ChartPoint[] = periods.map(
    (period) => {
      const features =
        period.features_percentage_points

      return {
        fiscalPeriod:
          period.fiscal_period ?? 'Unknown',
        asOf: period.as_of,
        growthGap: numberOrNull(
          features?.capex_growth_gap,
        ),
        intensityYoY: numberOrNull(
          features?.capex_intensity_yoy_delta,
        ),
        fcfMarginYoY: numberOrNull(
          features?.fcf_margin_yoy_delta,
        ),
        growthGapQoQ: numberOrNull(
          features?.capex_growth_gap_qoq_delta,
        ),
        intensityQoQ: numberOrNull(
          features
            ?.capex_intensity_yoy_delta_qoq_delta,
        ),
        fcfQoQ: numberOrNull(
          features
            ?.fcf_margin_yoy_delta_qoq_delta,
        ),
      }
    },
  )

  return (
    <div className="history-charts">
      <article className="chart-panel">
        <div className="chart-heading">
          <div>
            <h3>Structural pressure</h3>

            <p>
              Year-over-year capital-cycle features
              in percentage points.
            </p>
          </div>

          <span className="chart-axis-note">
            Gap: left axis · Margins: right axis
          </span>
        </div>

        <div className="chart-container">
          <ResponsiveContainer
            width="100%"
            height="100%"
          >
            <LineChart
              data={chartData}
              syncId="capital-cycle-history"
              margin={{
                top: 12,
                right: 8,
                bottom: 4,
                left: 0,
              }}
            >
              <CartesianGrid
                stroke="#283142"
                strokeDasharray="3 3"
                vertical={false}
              />

              <XAxis
                dataKey="fiscalPeriod"
                tick={{
                  fill: '#8792a7',
                  fontSize: 11,
                }}
                axisLine={{
                  stroke: '#344054',
                }}
                tickLine={false}
                minTickGap={26}
              />

              <YAxis
                yAxisId="gap"
                tick={{
                  fill: '#8792a7',
                  fontSize: 11,
                }}
                axisLine={false}
                tickLine={false}
                width={44}
                unit=" pp"
              />

              <YAxis
                yAxisId="margins"
                orientation="right"
                tick={{
                  fill: '#8792a7',
                  fontSize: 11,
                }}
                axisLine={false}
                tickLine={false}
                width={44}
                unit=" pp"
              />

              <ReferenceLine
                yAxisId="gap"
                y={0}
                stroke="#596579"
                strokeDasharray="4 4"
              />

              <Tooltip
                contentStyle={{
                  border: '1px solid #354158',
                  borderRadius: '8px',
                  background: '#111620',
                }}
                labelStyle={{
                  color: '#f2f5fa',
                  fontWeight: 700,
                }}
                itemStyle={{
                  color: '#c5cede',
                }}
              />

              <Legend
                wrapperStyle={{
                  paddingTop: '12px',
                  fontSize: '12px',
                }}
              />

              <Line
                yAxisId="gap"
                type="monotone"
                dataKey="growthGap"
                name="Growth gap"
                stroke="#8fb8ff"
                strokeWidth={2.5}
                dot={false}
                activeDot={{
                  r: 4,
                }}
                connectNulls={false}
                unit=" pp"
                isAnimationActive={false}
              />

              <Line
                yAxisId="margins"
                type="monotone"
                dataKey="intensityYoY"
                name="CAPEX intensity YoY"
                stroke="#e7b75f"
                strokeWidth={2}
                dot={false}
                activeDot={{
                  r: 4,
                }}
                connectNulls={false}
                unit=" pp"
                isAnimationActive={false}
              />

              <Line
                yAxisId="margins"
                type="monotone"
                dataKey="fcfMarginYoY"
                name="FCF margin YoY"
                stroke="#75d4a4"
                strokeWidth={2}
                dot={false}
                activeDot={{
                  r: 4,
                }}
                connectNulls={false}
                unit=" pp"
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </article>

      <article className="chart-panel">
        <div className="chart-heading">
          <div>
            <h3>Quarterly momentum</h3>

            <p>
              Change in the year-over-year features
              from the preceding fiscal quarter.
            </p>
          </div>

          <span className="chart-axis-note">
            Gap: left axis · Margins: right axis
          </span>
        </div>

        <div className="chart-container">
          <ResponsiveContainer
            width="100%"
            height="100%"
          >
            <LineChart
              data={chartData}
              syncId="capital-cycle-history"
              margin={{
                top: 12,
                right: 8,
                bottom: 4,
                left: 0,
              }}
            >
              <CartesianGrid
                stroke="#283142"
                strokeDasharray="3 3"
                vertical={false}
              />

              <XAxis
                dataKey="fiscalPeriod"
                tick={{
                  fill: '#8792a7',
                  fontSize: 11,
                }}
                axisLine={{
                  stroke: '#344054',
                }}
                tickLine={false}
                minTickGap={26}
              />

              <YAxis
                yAxisId="gap"
                tick={{
                  fill: '#8792a7',
                  fontSize: 11,
                }}
                axisLine={false}
                tickLine={false}
                width={44}
                unit=" pp"
              />

              <YAxis
                yAxisId="margins"
                orientation="right"
                tick={{
                  fill: '#8792a7',
                  fontSize: 11,
                }}
                axisLine={false}
                tickLine={false}
                width={44}
                unit=" pp"
              />

              <ReferenceLine
                yAxisId="gap"
                y={0}
                stroke="#596579"
                strokeDasharray="4 4"
              />

              <Tooltip
                contentStyle={{
                  border: '1px solid #354158',
                  borderRadius: '8px',
                  background: '#111620',
                }}
                labelStyle={{
                  color: '#f2f5fa',
                  fontWeight: 700,
                }}
                itemStyle={{
                  color: '#c5cede',
                }}
              />

              <Legend
                wrapperStyle={{
                  paddingTop: '12px',
                  fontSize: '12px',
                }}
              />

              <Line
                yAxisId="gap"
                type="monotone"
                dataKey="growthGapQoQ"
                name="Growth-gap QoQ"
                stroke="#8fb8ff"
                strokeWidth={2.5}
                dot={false}
                activeDot={{
                  r: 4,
                }}
                connectNulls={false}
                unit=" pp"
                isAnimationActive={false}
              />

              <Line
                yAxisId="margins"
                type="monotone"
                dataKey="intensityQoQ"
                name="Intensity QoQ"
                stroke="#e7b75f"
                strokeWidth={2}
                dot={false}
                activeDot={{
                  r: 4,
                }}
                connectNulls={false}
                unit=" pp"
                isAnimationActive={false}
              />

              <Line
                yAxisId="margins"
                type="monotone"
                dataKey="fcfQoQ"
                name="FCF QoQ"
                stroke="#75d4a4"
                strokeWidth={2}
                dot={false}
                activeDot={{
                  r: 4,
                }}
                connectNulls={false}
                unit=" pp"
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </article>
    </div>
  )
}

export default CapitalCycleCharts
