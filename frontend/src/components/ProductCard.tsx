import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import { Box, Card, CardActionArea, Chip, Stack, Tooltip, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import type { ProductSummary } from '../api/types'
import { CATEGORY_LABELS } from '../format'
import { useCurrency } from '../currency'
import { ProductImage } from './ProductImage'

interface Props {
  product: ProductSummary
  /** Show how much the price varies between retailers - the reason to compare. */
  showSpread?: boolean
}

export function ProductCard({ product, showSpread = true }: Props) {
  const { formatPrice } = useCurrency()
  const spread =
    product.best_price !== null && product.highest_price !== null
      ? product.highest_price - product.best_price
      : 0

  // One badge, not one chip per hit - the card is a summary, and the product
  // page spells out exactly which ingredients matched.
  const hits = product.allergens?.hits ?? []

  return (
    <Card
      sx={{
        height: '100%',
        '&:hover': { borderColor: 'primary.light', transform: 'translateY(-2px)' },
      }}
    >
      <CardActionArea
        component={RouterLink}
        to={`/product/${product.slug}`}
        sx={{
          height: '100%',
          p: 2.25,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'stretch',
          gap: 1.6,
        }}
      >
        <ProductImage
          src={product.image_url}
          alt={`${product.brand} ${product.name}`}
          fallbackLabel={product.brand}
        />

        <Stack spacing={0.6} sx={{ flexGrow: 1 }}>
          {/* Brand as an eyebrow: it identifies without competing with the name. */}
          <Typography
            sx={{
              fontSize: '0.72rem',
              fontWeight: 600,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'text.secondary',
              lineHeight: 1.3,
            }}
          >
            {product.brand}
          </Typography>

          <Typography sx={{ fontSize: '0.95rem', fontWeight: 600, lineHeight: 1.35 }}>
            {product.name}
          </Typography>

          <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
            {CATEGORY_LABELS[product.category] ?? product.category}
            {product.size_label ? ` · ${product.size_label}` : ''}
          </Typography>
        </Stack>

        {hits.length > 0 ? (
          <Tooltip title={hits.map((hit) => hit.summary).join(' · ')}>
            <Chip
              icon={<ErrorOutlineIcon />}
              label={`Contains ${hits.length} you avoid`}
              size="small"
              color="error"
              variant="outlined"
              sx={{ alignSelf: 'flex-start' }}
            />
          </Tooltip>
        ) : product.allergens?.verdict === 'clear' ? (
          <Chip
            label="No listed allergens"
            size="small"
            color="success"
            variant="outlined"
            sx={{ alignSelf: 'flex-start' }}
          />
        ) : (
          product.key_actives.length > 0 && (
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              {product.key_actives.slice(0, 2).map((active) => (
                <Chip key={active} label={active} size="small" variant="outlined" />
              ))}
            </Stack>
          )
        )}

        {/* A hairline separates the money from the description, so the price
            reads as the conclusion rather than as one more line of metadata. */}
        <Box sx={{ pt: 1.6, borderTop: 1, borderColor: 'divider' }}>
          {product.best_price !== null ? (
            <Stack direction="row" alignItems="baseline" spacing={1} flexWrap="wrap" useFlexGap>
              <Typography
                component="span"
                sx={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.025em' }}
              >
                {formatPrice(product.best_price)}
              </Typography>
              {showSpread && spread > 0.5 ? (
                <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                  to {formatPrice(product.highest_price)}
                </Typography>
              ) : (
                <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                  {product.retailer_count > 0
                    ? `${product.retailer_count} retailer${product.retailer_count === 1 ? '' : 's'}`
                    : 'Not currently stocked'}
                </Typography>
              )}
              {product.on_sale && (
                <Chip label="On sale" size="small" color="secondary" variant="outlined" />
              )}
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              No price available
            </Typography>
          )}
        </Box>
      </CardActionArea>
    </Card>
  )
}
