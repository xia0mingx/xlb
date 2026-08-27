import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import {
  Alert,
  Box,
  Breadcrumbs,
  Button,
  Chip,
  Container,
  Divider,
  Grid,
  Link,
  Paper,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { Link as RouterLink, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { IngredientList } from '../components/IngredientList'
import { PriceChart } from '../components/PriceChart'
import { PriceTable } from '../components/PriceTable'
import { ProductCard } from '../components/ProductCard'
import { ProductImage } from '../components/ProductImage'
import { CATEGORY_LABELS } from '../format'
import { useCurrency } from '../currency'
import { useSkinProfile } from '../hooks/useSkinProfile'

export function Product() {
  const { formatPrice } = useCurrency()
  const { slug = '' } = useParams()
  const { profile } = useSkinProfile()
  const avoid = profile?.avoid_ingredients ?? []

  // `avoid` is in the key so editing the profile refetches rather than serving
  // a cached, unscreened copy.
  const { data: product, isLoading, isError } = useQuery({
    queryKey: ['product', slug, avoid],
    queryFn: () => api.product(slug, avoid),
    enabled: Boolean(slug),
  })

  const { data: history } = useQuery({
    queryKey: ['history', slug],
    queryFn: () => api.priceHistory(slug, 90),
    enabled: Boolean(slug),
  })

  const { data: dupes } = useQuery({
    queryKey: ['dupes', slug],
    queryFn: () => api.dupes(slug),
    enabled: Boolean(slug),
  })

  if (isLoading) {
    return (
      <Container maxWidth="lg" sx={{ py: 6 }}>
        <Skeleton variant="text" width={260} height={48} />
        <Skeleton variant="rounded" height={320} sx={{ mt: 3 }} />
      </Container>
    )
  }

  if (isError || !product) {
    return (
      <Container maxWidth="sm" sx={{ py: 10, textAlign: 'center' }}>
        <Typography variant="h3" sx={{ mb: 1.5 }}>
          Product not found
        </Typography>
        <Button component={RouterLink} to="/search" startIcon={<ArrowBackIcon />}>
          Back to search
        </Button>
      </Container>
    )
  }

  const saving =
    product.best_price !== null && product.highest_price !== null
      ? product.highest_price - product.best_price
      : 0

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
      <Breadcrumbs sx={{ mb: 3 }}>
        <Link component={RouterLink} to="/" underline="hover" color="inherit">
          Home
        </Link>
        <Link
          component={RouterLink}
          to={`/search?category=${product.category}`}
          underline="hover"
          color="inherit"
        >
          {CATEGORY_LABELS[product.category] ?? product.category}
        </Link>
        <Typography color="text.primary">{product.name}</Typography>
      </Breadcrumbs>

      <Grid container spacing={5}>
        <Grid item xs={12} md={7}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={{ xs: 2, sm: 3 }}
            alignItems="flex-start"
          >
            <Box sx={{ width: { xs: '100%', sm: 200 }, flexShrink: 0 }}>
              <ProductImage
                src={product.image_url}
                alt={`${product.brand} ${product.name}`}
                fallbackLabel={product.brand}
              />
            </Box>

            <Stack spacing={1} sx={{ minWidth: 0, flexGrow: 1 }}>
            <Link
              component={RouterLink}
              to={`/search?q=${encodeURIComponent(product.brand)}`}
              underline="hover"
              variant="overline"
              color="text.secondary"
            >
              {product.brand}
            </Link>
            <Typography variant="h1" sx={{ fontSize: { xs: '1.9rem', md: '2.4rem' } }}>
              {product.name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {CATEGORY_LABELS[product.category] ?? product.category}
              {product.size_label ? ` · ${product.size_label}` : ''}
            </Typography>

            {product.concerns.length > 0 && (
              <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ pt: 1 }}>
                {product.concerns.map((concern) => (
                  <Chip
                    key={concern}
                    component={RouterLink}
                    to={`/search?concern=${concern}`}
                    clickable
                    size="small"
                    variant="outlined"
                    label={concern.replace('_', ' ')}
                    sx={{ textTransform: 'capitalize' }}
                  />
                ))}
              </Stack>
            )}

            {product.description && (
              <Typography variant="body2" color="text.secondary" sx={{ pt: 1.5 }}>
                {product.description}
              </Typography>
            )}
            </Stack>
          </Stack>
        </Grid>

        <Grid item xs={12} md={5}>
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Typography variant="overline" color="text.secondary">
              Best price
            </Typography>
            <Typography variant="h2" sx={{ my: 0.5 }}>
              {formatPrice(product.best_price)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              across {product.retailer_count} retailer
              {product.retailer_count === 1 ? '' : 's'}
              {saving > 0.5 ? ` · save ${formatPrice(saving)} vs the dearest` : ''}
            </Typography>
            {product.lowest_90d !== null && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                90-day range {formatPrice(product.lowest_90d)} – {formatPrice(product.highest_90d)}
                {product.best_price !== null &&
                product.lowest_90d !== null &&
                product.best_price <= product.lowest_90d * 1.02
                  ? ' · at its lowest'
                  : ''}
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>

      <Box sx={{ mt: 6 }}>
        <Typography variant="h3" sx={{ mb: 2 }}>
          Where to buy
        </Typography>
        <PriceTable prices={product.prices} />
      </Box>

      <Box sx={{ mt: 6 }}>
        <PriceChart history={history ?? []} lowest={product.lowest_90d} />
      </Box>

      <Box sx={{ mt: 6 }}>
        <Stack direction="row" alignItems="baseline" spacing={1.5} sx={{ mb: 2 }}>
          <Typography variant="h3">Ingredients</Typography>
          <Typography variant="body2" color="text.secondary">
            {product.ingredients.length} listed
          </Typography>
        </Stack>
        <IngredientList
          ingredients={product.ingredients}
          analysis={product.analysis}
          allergens={product.allergens}
        />
      </Box>

      {dupes && dupes.length > 0 && (
        <Box sx={{ mt: 6 }}>
          <Divider sx={{ mb: 4 }} />
          <Stack spacing={0.5} sx={{ mb: 2.5 }}>
            <Typography variant="h3">Cheaper alternatives</Typography>
            <Typography variant="body2" color="text.secondary">
              Similar ingredient profiles in the same category, at a lower price.
            </Typography>
          </Stack>

          <Grid container spacing={2.5}>
            {dupes.map((dupe) => (
              <Grid item xs={12} sm={6} md={3} key={dupe.product.id}>
                <Stack spacing={1} sx={{ height: '100%' }}>
                  <ProductCard product={dupe.product} showSpread={false} />
                  <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                    <Chip
                      size="small"
                      color="primary"
                      variant="outlined"
                      label={`${Math.round(dupe.similarity * 100)}% similar`}
                    />
                    {dupe.savings !== null && dupe.savings > 0 && (
                      <Chip
                        size="small"
                        color="success"
                        variant="outlined"
                        label={`save ${formatPrice(dupe.savings)}`}
                      />
                    )}
                  </Stack>
                  {dupe.shared_actives.length > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      Shares {dupe.shared_actives.slice(0, 2).join(', ')}
                    </Typography>
                  )}
                </Stack>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {dupes && dupes.length === 0 && (
        <Alert severity="info" variant="outlined" sx={{ mt: 6 }}>
          No cheaper alternative with a comparable ingredient profile in our catalog.
        </Alert>
      )}
    </Container>
  )
}
