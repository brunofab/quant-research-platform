import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
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
  selectedPeriodIndex: number
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

type SeriesKey =
  | 'growthGap'
  | 'intensityYoY'
  | 'fcfMarginYoY'
  | 'growthGapQoQ'
  | 'intensityQoQ'
  | 'fcfQoQ'

type ChartSeries = {
  dataKey: SeriesKey
  name: string
  axis: 'gap' | 'margins'
  stroke: string
  strokeWidth: number
}

type MetricChartProps = {
  title: string
  description: string
  data: ChartPoint[]
  selectedPoint: ChartPoint | null
  series: ChartSeries[]
}

function numberOrNull(
  value: number | undefined,
): number | null {
  return value ?? null
}

function MetricChart({
  title,
  description,
  data,
  selectedPoint,
  series,
}: MetricChartProps) {
  return (
    <article className="chart-panel">
      <div className="chart-heading">
        <div>
          <h3>{title}</h3>

          <p>{description}</p>
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
            data={data}
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

            {selectedPoint && (
              <ReferenceLine
                yAxisId="gap"
                x={selectedPoint.fiscalPeriod}
                stroke="#9fc5ff"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                zIndex={500}
              />
            )}

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

            {series.map((item) => (
              <Line
                key={item.dataKey}
                yAxisId={item.axis}
                type="monotone"
                dataKey={item.dataKey}
                name={item.name}
                stroke={item.stroke}
                strokeWidth={item.strokeWidth}
                dot={false}
                activeDot={{
                  r: 4,
                }}
                connectNulls={false}
                unit=" pp"
                isAnimationActive={false}
              />
            ))}

            {selectedPoint &&
              series.map((item) => {
                const value =
                  selectedPoint[item.dataKey]

                if (value === null) {
                  return null
                }

                return (
                  <ReferenceDot
                    key={item.dataKey}
                    yAxisId={item.axis}
                    x={selectedPoint.fiscalPeriod}
                    y={value}
                    r={5}
                    fill={item.stroke}
                    stroke="#0c0f15"
                    strokeWidth={2}
                    zIndex={700}
                  />
                )
              })}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </article>
  )
}

const STRUCTURAL_SERIES: ChartSeries[] = [
  {
    dataKey: 'growthGap',
    name: 'Growth gap',
    axis: 'gap',
    stroke: '#8fb8ff',
    strokeWidth: 2.5,
  },
  {
    dataKey: 'intensityYoY',
    name: 'CAPEX intensity YoY',
    axis: 'margins',
    stroke: '#e7b75f',
    strokeWidth: 2,
  },
  {
    dataKey: 'fcfMarginYoY',
    name: 'FCF margin YoY',
    axis: 'margins',
    stroke: '#75d4a4',
    strokeWidth: 2,
  },
]

const MOMENTUM_SERIES: ChartSeries[] = [
  {
    dataKey: 'growthGapQoQ',
    name: 'Growth-gap QoQ',
    axis: 'gap',
    stroke: '#8fb8ff',
    strokeWidth: 2.5,
  },
  {
    dataKey: 'intensityQoQ',
    name: 'Intensity QoQ',
    axis: 'margins',
    stroke: '#e7b75f',
    strokeWidth: 2,
  },
  {
    dataKey: 'fcfQoQ',
    name: 'FCF QoQ',
    axis: 'margins',
    stroke: '#75d4a4',
    strokeWidth: 2,
  },
]

function CapitalCycleCharts({
  periods,
  selectedPeriodIndex,
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

  const effectiveSelectedIndex =
    selectedPeriodIndex >= 0 &&
    selectedPeriodIndex < chartData.length
      ? selectedPeriodIndex
      : chartData.length - 1

  const selectedPoint =
    chartData[effectiveSelectedIndex] ?? null

  return (
    <div className="history-charts">
      <MetricChart
        title="Structural pressure"
        description={
          'Year-over-year capital-cycle features ' +
          'in percentage points.'
        }
        data={chartData}
        selectedPoint={selectedPoint}
        series={STRUCTURAL_SERIES}
      />

      <MetricChart
        title="Quarterly momentum"
        description={
          'Change in the year-over-year features ' +
          'from the preceding fiscal quarter.'
        }
        data={chartData}
        selectedPoint={selectedPoint}
        series={MOMENTUM_SERIES}
      />
    </div>
  )
}

export default CapitalCycleCharts