import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import {
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material'
import type { RetailerPrice } from '../api/types'
import { formatRelativeTime } from '../format'
import { useCurrency } from '../currency'

interface Props {
  prices: RetailerPrice[]
}

export function PriceTable({ prices }: Props) {
  const { formatPrice } = useCurrency()
  if (prices.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          No retailer prices for this product yet.
        </Typography>
      </Paper>
    )
  }

  const best = prices.find((p) => p.is_best)
  const worst = [...prices]
    .filter((p) => p.price !== null)
    .sort((a, b) => (b.price ?? 0) - (a.price ?? 0))[0]
  const saving = best?.price && worst?.price ? worst.price - best.price : 0

  return (
    <Stack spacing={1.5}>
      {saving > 0.5 && (
        <Typography variant="body2" color="text.secondary">
          Same product, {formatPrice(saving)} apart — cheapest at{' '}
          <Box component="span" sx={{ fontWeight: 600, color: 'text.primary' }}>
            {best?.retailer}
          </Box>
          .
        </Typography>
      )}

      <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
        <Table size="small" sx={{ minWidth: 520 }}>
          <TableHead>
            <TableRow>
              <TableCell>Retailer</TableCell>
              <TableCell align="right">Price</TableCell>
              <TableCell>Availability</TableCell>
              <TableCell>Updated</TableCell>
              <TableCell align="right" />
            </TableRow>
          </TableHead>
          <TableBody>
            {prices.map((price) => (
              <TableRow
                key={price.retailer_slug}
                sx={{
                  backgroundColor: price.is_best ? 'rgba(63, 111, 95, 0.06)' : undefined,
                }}
              >
                <TableCell>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Typography variant="body2" sx={{ fontWeight: price.is_best ? 600 : 400 }}>
                      {price.retailer}
                    </Typography>
                    {price.is_best && <Chip label="Best" size="small" color="primary" />}
                  </Stack>
                </TableCell>

                <TableCell align="right">
                  <Stack direction="row" spacing={1} justifyContent="flex-end" alignItems="baseline">
                    {price.was_price && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ textDecoration: 'line-through' }}
                      >
                        {formatPrice(price.was_price)}
                      </Typography>
                    )}
                    <Typography
                      variant="body2"
                      sx={{ fontWeight: 600, color: price.was_price ? 'secondary.main' : undefined }}
                    >
                      {formatPrice(price.price)}
                    </Typography>
                  </Stack>
                </TableCell>

                <TableCell>
                  <Typography variant="caption" color={price.in_stock ? 'success.main' : 'text.secondary'}>
                    {price.in_stock ? 'In stock' : 'Out of stock'}
                  </Typography>
                </TableCell>

                <TableCell>
                  {/* A stale price is shown with its age rather than hidden - an old
                      price the user can judge beats a blank cell. */}
                  <Tooltip
                    title={
                      price.is_stale
                        ? 'This retailer could not be refreshed recently, so the price may be out of date.'
                        : ''
                    }
                  >
                    <Typography
                      variant="caption"
                      color={price.is_stale ? 'warning.main' : 'text.secondary'}
                    >
                      {formatRelativeTime(price.last_scraped_at)}
                      {price.is_stale ? ' · stale' : ''}
                    </Typography>
                  </Tooltip>
                </TableCell>

                <TableCell align="right">
                  <Button
                    size="small"
                    endIcon={<OpenInNewIcon sx={{ fontSize: 14 }} />}
                    href={price.url}
                    target="_blank"
                    rel="noopener noreferrer nofollow"
                  >
                    Visit
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  )
}
