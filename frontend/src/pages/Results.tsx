import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import LightModeIcon from '@mui/icons-material/LightMode'
import NightsStayIcon from '@mui/icons-material/NightsStay'
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  Container,
  Grid,
  Paper,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { Link as RouterLink } from 'react-router-dom'
import { api } from '../api/client'
import type { ProductSummary } from '../api/types'
import { ProductCard } from '../components/ProductCard'
import { CATEGORY_LABELS } from '../format'
import { useCurrency } from '../currency'
import { useSkinProfile } from '../hooks/useSkinProfile'

function RoutineColumn({
  title,
  icon,
  products,
}: {
  title: string
  icon: React.ReactNode
  products: ProductSummary[]
}) {
  const { formatPrice } = useCurrency()
  return (
    <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        {icon}
        <Typography variant="h5">{title}</Typography>
      </Stack>
      <Stack spacing={1.5}>
        {products.map((product, index) => (
          <Stack key={product.id} direction="row" spacing={1.5} alignItems="baseline">
            <Typography variant="caption" color="text.secondary" sx={{ minWidth: 18 }}>
              {index + 1}.
            </Typography>
            <Box>
              <Typography
                component={RouterLink}
                to={`/product/${product.slug}`}
                variant="body2"
                sx={{ fontWeight: 600, color: 'text.primary', textDecoration: 'none' }}
              >
                {product.brand} {product.name}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                {CATEGORY_LABELS[product.category] ?? product.category} ·{' '}
                {formatPrice(product.best_price)}
              </Typography>
            </Box>
          </Stack>
        ))}
        {products.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            Nothing recommended for this step.
          </Typography>
        )}
      </Stack>
    </Paper>
  )
}

export function Results() {
  const { profile, hasProfile } = useSkinProfile()

  const { data, isLoading } = useQuery({
    queryKey: ['recommendations', profile],
    queryFn: () => api.recommend({ ...profile!, limit: 12 }),
    enabled: hasProfile,
  })

  if (!hasProfile) {
    return (
      <Container maxWidth="sm" sx={{ py: 10, textAlign: 'center' }}>
        <Typography variant="h3" sx={{ mb: 1.5 }}>
          Take the quiz first
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
          Four questions and we can match products to your skin.
        </Typography>
        <Button component={RouterLink} to="/quiz" variant="contained" size="large">
          Start the quiz
        </Button>
      </Container>
    )
  }

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ sm: 'flex-end' }}
        spacing={2}
        sx={{ mb: 4 }}
      >
        <Stack spacing={0.5}>
          <Typography variant="h1" sx={{ fontSize: { xs: '2rem', md: '2.4rem' } }}>
            Built for your skin
          </Typography>
          <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ pt: 1 }}>
            <Chip size="small" label={`${profile!.skin_type} skin`} sx={{ textTransform: 'capitalize' }} />
            {profile!.concerns.map((concern) => (
              <Chip key={concern} size="small" variant="outlined" label={concern.replace('_', ' ')} sx={{ textTransform: 'capitalize' }} />
            ))}
            {profile!.sensitive && <Chip size="small" variant="outlined" label="sensitive" />}
            {profile!.avoid_ingredients.map((term) => (
              <Chip key={term} size="small" color="error" variant="outlined" label={`avoiding ${term}`} />
            ))}
            {profile!.budget_max && <Chip size="small" variant="outlined" label={`under $${profile!.budget_max}`} />}
          </Stack>
        </Stack>
        <Button component={RouterLink} to="/quiz" variant="outlined">
          Retake quiz
        </Button>
      </Stack>

      {isLoading && <Skeleton variant="rounded" height={280} />}

      {data && data.excluded.length > 0 && (
        <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
          <AlertTitle>
            {data.excluded.length} product{data.excluded.length === 1 ? '' : 's'} hidden for your
            allergies
          </AlertTitle>
          <Stack component="ul" spacing={0.25} sx={{ m: 0, pl: 2.5 }}>
            {data.excluded.slice(0, 5).map((item) => (
              <Typography component="li" variant="body2" key={item.slug}>
                {item.brand} {item.name} — {item.hits[0]?.summary}
              </Typography>
            ))}
          </Stack>
          {data.excluded.length > 5 && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              and {data.excluded.length - 5} more.
            </Typography>
          )}
        </Alert>
      )}

      {data && data.allergen_terms.some((term) => !term.recognized) && (
        <Alert severity="warning" variant="outlined" sx={{ mb: 2 }}>
          We don't recognise{' '}
          {data.allergen_terms
            .filter((term) => !term.recognized)
            .map((term) => `"${term.query}"`)
            .join(', ')}
          , so we searched for that wording exactly as you typed it. Check the spelling, or use
          the INCI name from the pack.
        </Alert>
      )}

      {data && data.conflicts.length > 0 && (
        <Stack spacing={1.5} sx={{ mb: 4 }}>
          {data.conflicts.map((conflict) => (
            <Alert
              key={conflict.id}
              severity={conflict.severity === 'high' ? 'error' : conflict.severity === 'medium' ? 'warning' : 'info'}
              variant="outlined"
              icon={<ErrorOutlineIcon fontSize="inherit" />}
            >
              <AlertTitle>{conflict.title}</AlertTitle>
              <Typography variant="body2" sx={{ mb: 0.75 }}>
                {conflict.explanation}
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {conflict.guidance}
              </Typography>
              {conflict.products.length > 0 && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.75 }}>
                  Between: {conflict.products.join(' and ')}
                </Typography>
              )}
            </Alert>
          ))}
        </Stack>
      )}

      {data && (data.routine.am.length > 0 || data.routine.pm.length > 0) && (
        <Box sx={{ mb: 6 }}>
          <Typography variant="h3" sx={{ mb: 2 }}>
            Your suggested routine
          </Typography>
          <Grid container spacing={2.5}>
            <Grid item xs={12} md={6}>
              <RoutineColumn
                title="Morning"
                icon={<LightModeIcon sx={{ color: 'warning.main' }} />}
                products={data.routine.am}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <RoutineColumn
                title="Evening"
                icon={<NightsStayIcon sx={{ color: 'primary.main' }} />}
                products={data.routine.pm}
              />
            </Grid>
          </Grid>
        </Box>
      )}

      <Typography variant="h3" sx={{ mb: 2.5 }}>
        Recommended products
      </Typography>

      <Grid container spacing={2.5}>
        {data?.recommendations.map((rec) => (
          <Grid item xs={12} sm={6} md={4} key={rec.product.id}>
            <Stack spacing={1.25} sx={{ height: '100%' }}>
              <ProductCard product={rec.product} />
              <Stack spacing={0.5}>
                {rec.reasons.slice(0, 3).map((reason) => (
                  <Stack key={reason} direction="row" spacing={0.75} alignItems="flex-start">
                    <CheckCircleOutlineIcon sx={{ fontSize: 15, color: 'success.main', mt: '2px' }} />
                    <Typography variant="caption" color="text.secondary">
                      {reason}
                    </Typography>
                  </Stack>
                ))}
                {rec.warnings.slice(0, 2).map((warning) => (
                  <Stack key={warning} direction="row" spacing={0.75} alignItems="flex-start">
                    <ErrorOutlineIcon sx={{ fontSize: 15, color: 'warning.main', mt: '2px' }} />
                    <Typography variant="caption" color="warning.main">
                      {warning}
                    </Typography>
                  </Stack>
                ))}
              </Stack>
            </Stack>
          </Grid>
        ))}
      </Grid>

      {data && data.recommendations.length === 0 && (
        <Paper variant="outlined" sx={{ p: 5, textAlign: 'center' }}>
          <Typography variant="h5" sx={{ mb: 1 }}>
            Nothing scored well enough
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {data.excluded.length > 0
              ? `Try widening your budget or selecting another concern — ${data.excluded.length} product${data.excluded.length === 1 ? ' was' : 's were'} also removed for your allergies.`
              : 'Try widening your budget or selecting another concern.'}
          </Typography>
        </Paper>
      )}
    </Container>
  )
}
