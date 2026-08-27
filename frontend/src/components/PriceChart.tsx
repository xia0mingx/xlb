import { Paper, Stack, Typography, useTheme } from '@mui/material'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { PriceHistory } from '../api/types'
import { SERIES_COLORS } from '../format'
import { useCurrency } from '../currency'

interface Props {
  history: PriceHistory[]
  lowest?: number | null
}

/**
 * Retailers are sampled at slightly different times, so the series are merged
 * onto a shared date axis rather than plotted independently - otherwise the
 * lines cannot be compared at a glance, which is the whole point.
 */
/**
 * Flatten the per-retailer series into one row per day, converting as we go.
 *
 * Conversion happens here rather than in the formatters so that the plotted
 * positions, the axis ticks and the tooltip all read from the same numbers. Doing
 * it in the formatters instead would leave the line drawn at the USD value while
 * the labels claimed another currency.
 */
function mergeSeries(history: PriceHistory[], convert: (value: number) => number) {
  const byDate = new Map<string, Record<string, number | string>>()

  history.forEach((series) => {
    series.points.forEach((point) => {
      const day = point.date.slice(0, 10)
      const row = byDate.get(day) ?? { date: day }
      row[series.retailer_slug] = convert(point.price)
      byDate.set(day, row)
    })
  })

  return Array.from(byDate.values()).sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  )
}

export function PriceChart({ history, lowest }: Props) {
  const { formatPrice, convert, currency } = useCurrency()
  const theme = useTheme()

  if (history.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          No price history recorded yet.
        </Typography>
      </Paper>
    )
  }

  const data = mergeSeries(history, convert)

  return (
    <Paper variant="outlined" sx={{ p: 2.5 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ sm: 'baseline' }}
        spacing={0.5}
        sx={{ mb: 2 }}
      >
        <Typography variant="h5">Price history</Typography>
        {lowest !== null && lowest !== undefined && (
          <Typography variant="caption" color="text.secondary">
            90-day low: <strong>{formatPrice(lowest)}</strong>
          </Typography>
        )}
      </Stack>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -12 }}>
          <CartesianGrid stroke={theme.palette.divider} vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: theme.palette.text.secondary }}
            tickFormatter={(value: string) => value.slice(5)}
            minTickGap={28}
            stroke={theme.palette.divider}
          />
          <YAxis
            tick={{ fontSize: 11, fill: theme.palette.text.secondary }}
            tickFormatter={(value: number) => `${currency.symbol}${value}`}
            width={54}
            stroke={theme.palette.divider}
            domain={['auto', 'auto']}
          />
          <Tooltip
            formatter={(value: number, name: string) => [
              // Already converted in mergeSeries - only add the symbol here.
              `${currency.symbol}${value.toFixed(2)}`,
              history.find((h) => h.retailer_slug === name)?.retailer ?? name,
            ]}
            contentStyle={{
              borderRadius: 10,
              border: `1px solid ${theme.palette.divider}`,
              fontSize: 13,
            }}
          />
          <Legend
            formatter={(value: string) =>
              history.find((h) => h.retailer_slug === value)?.retailer ?? value
            }
            wrapperStyle={{ fontSize: 12 }}
          />
          {history.map((series, index) => (
            <Line
              key={series.retailer_slug}
              type="monotone"
              dataKey={series.retailer_slug}
              stroke={SERIES_COLORS[index % SERIES_COLORS.length]}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Paper>
  )
}
