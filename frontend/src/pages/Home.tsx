import HealthAndSafetyIcon from '@mui/icons-material/HealthAndSafety'
import SearchIcon from '@mui/icons-material/Search'
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Grid,
  InputAdornment,
  Paper,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { AllergyPicker } from '../components/AllergyPicker'
import { ProductCard } from '../components/ProductCard'
import { CATEGORY_LABELS } from '../format'
import { useSkinProfile } from '../hooks/useSkinProfile'

export function Home() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const { profile, hasProfile } = useSkinProfile()
  const avoid = profile?.avoid_ingredients ?? []

  const { data: filters } = useQuery({ queryKey: ['filters'], queryFn: api.filters })
  const { data: deals, isLoading } = useQuery({
    queryKey: ['deals', avoid],
    queryFn: () => api.deals(8, avoid),
  })

  const flagged = (deals ?? []).filter((product) => (product.allergens?.hits.length ?? 0) > 0)

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    navigate(`/search?q=${encodeURIComponent(query.trim())}`)
  }

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 5, md: 8 } }}>
      <Stack spacing={2.5} sx={{ maxWidth: 720, mb: 7 }}>
        <Typography
          sx={{
            fontSize: '0.72rem',
            fontWeight: 600,
            letterSpacing: '0.13em',
            textTransform: 'uppercase',
            color: 'secondary.main',
          }}
        >
          Skincare price comparison
        </Typography>
        <Typography
          variant="h1"
          sx={{
            fontSize: { xs: '2.4rem', md: '3.6rem' },
            lineHeight: 1.05,
            letterSpacing: '-0.035em',
          }}
        >
          Know what is in it.
          <Box component="span" sx={{ color: 'primary.main', display: 'block' }}>
            Pay less for it.
          </Box>
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ fontSize: '1.1rem' }}>
          Compare the same skincare product across retailers, read the full ingredient
          list with the actives and irritants called out, and get recommendations built
          around your skin — not around what is on offer this week.
        </Typography>

        <Box component="form" onSubmit={submit}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField
              fullWidth
              placeholder="Search a product, brand or ingredient"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />
            <Button type="submit" variant="contained" size="large" sx={{ px: 4 }}>
              Search
            </Button>
          </Stack>
        </Box>

        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <Button component={RouterLink} to="/quiz" variant="outlined" size="large">
            {hasProfile ? 'Retake the skin quiz' : 'Take the skin quiz'}
          </Button>
          {hasProfile && (
            <Button component={RouterLink} to="/results" size="large">
              See my recommendations
            </Button>
          )}
        </Stack>
      </Stack>

      <Paper
        variant="outlined"
        sx={{
          p: { xs: 2.5, md: 3 },
          mb: 7,
          borderLeft: 3,
          borderLeftColor: avoid.length ? 'error.main' : 'primary.main',
        }}
      >
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          sx={{ mb: 0.5 }}
        >
          <HealthAndSafetyIcon
            fontSize="small"
            sx={{ color: avoid.length ? 'error.main' : 'primary.main' }}
          />
          <Typography variant="h4">Anything you are allergic to?</Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
          Add it once and we will check every ingredient list against it — here, in search, on
          every product page, and when building your routine. Choosing a group catches the whole
          family: “fragrance” also finds Linalool, Limonene and the other 24 components the EU
          requires to be declared by name.
        </Typography>

        <AllergyPicker />

        {avoid.length > 0 && (
          <Alert
            severity={flagged.length > 0 ? 'warning' : 'success'}
            variant="outlined"
            sx={{ mt: 2.5 }}
          >
            {flagged.length > 0
              ? `${flagged.length} of the ${deals?.length ?? 0} product${deals?.length === 1 ? '' : 's'} below contain${flagged.length === 1 ? 's' : ''} something you avoid — look for the red badge.`
              : `Screening ${avoid.length} entr${avoid.length === 1 ? 'y' : 'ies'}. Nothing below contains them.`}
          </Alert>
        )}
      </Paper>

      {filters && filters.categories.length > 0 && (
        <Box sx={{ mb: 7 }}>
          <Typography variant="h4" sx={{ mb: 2 }}>
            Browse by category
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {filters.categories.map((category) => (
              <Chip
                key={category.key}
                component={RouterLink}
                to={`/search?category=${category.key}`}
                clickable
                label={`${CATEGORY_LABELS[category.key] ?? category.label} (${category.count})`}
                sx={{ px: 0.5 }}
              />
            ))}
          </Stack>
        </Box>
      )}

      <Box>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          justifyContent="space-between"
          alignItems={{ sm: 'baseline' }}
          spacing={0.5}
          sx={{ mb: 2.5, pb: 1.6, borderBottom: 1, borderColor: 'divider' }}
        >
          <Typography variant="h3">Biggest price gaps</Typography>
          <Typography variant="body2" color="text.secondary">
            Same product, very different prices depending on where you buy
          </Typography>
        </Stack>

        <Grid container spacing={2.5}>
          {isLoading &&
            Array.from({ length: 8 }).map((_, index) => (
              <Grid item xs={12} sm={6} md={3} key={index}>
                <Skeleton variant="rounded" height={210} />
              </Grid>
            ))}

          {deals?.map((product) => (
            <Grid item xs={12} sm={6} md={3} key={product.id}>
              <ProductCard product={product} />
            </Grid>
          ))}
        </Grid>
      </Box>
    </Container>
  )
}
