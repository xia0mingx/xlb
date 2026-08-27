import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import ScienceIcon from '@mui/icons-material/Science'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import {
  Alert,
  AlertTitle,
  Box,
  Chip,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material'
import type { AllergenScreen, Ingredient, ProductAnalysis } from '../api/types'
import { ACTIVE_GROUP_LABELS } from '../format'
import { ProvenanceBreakdown } from './ProvenanceBreakdown'

const COVERAGE_CAVEAT =
  'Screening compares your list against the published ingredient list. It cannot account for ' +
  'reformulation, cross-contamination, or "may contain" traces — check the pack if you react severely.'

const SOURCE_LABELS: Record<string, string> = {
  natural: 'natural',
  nature_identical: 'nature-identical',
  synthetic: 'synthetic',
}

function ordinal(n: number): string {
  const rem100 = n % 100
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`
  return `${n}${['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'}`
}

function formatList(items: string[]): string {
  const quoted = items.map((item) => `"${item}"`)
  if (quoted.length <= 1) return quoted.join('')
  return `${quoted.slice(0, -1).join(', ')} or ${quoted[quoted.length - 1]}`
}

interface Props {
  ingredients: Ingredient[]
  analysis: ProductAnalysis
  /** Null when the viewer has no avoid-list, so nothing was checked. */
  allergens?: AllergenScreen | null
}

export function IngredientList({ ingredients, analysis, allergens }: Props) {
  if (ingredients.length === 0) {
    return (
      <Alert severity="info" variant="outlined">
        {allergens
          ? 'No ingredient list on file, so we cannot screen this product against your allergies.'
          : 'No ingredient list available for this product yet.'}
      </Alert>
    )
  }

  const hits = allergens?.hits ?? []
  const flaggedNames = new Set(hits.map((hit) => hit.inci_name))
  // Position approximates concentration, so something listed 3rd matters more
  // than the same thing listed 30th. Highest tier wins for the banner.
  const anyProminent = hits.some((hit) => hit.prominent)

  const flags: string[] = []
  if (analysis.has_fragrance) flags.push('Contains fragrance')
  if (analysis.has_alcohol) flags.push('Contains denatured alcohol')
  if (analysis.has_essential_oil) flags.push('Contains essential oils')
  if (analysis.max_comedogenic >= 3) {
    flags.push(`Comedogenic ingredient rated ${analysis.max_comedogenic}/5`)
  }

  return (
    <Stack spacing={2}>
      {hits.length > 0 && (
        <Alert
          severity={anyProminent ? 'error' : 'warning'}
          variant="outlined"
          icon={<ErrorOutlineIcon fontSize="inherit" />}
        >
          <AlertTitle>
            Contains {hits.length} ingredient{hits.length === 1 ? '' : 's'} you avoid
          </AlertTitle>
          <Stack component="ul" spacing={0.25} sx={{ m: 0, pl: 2.5 }}>
            {hits.map((hit) => (
              <Typography component="li" variant="body2" key={`${hit.position}-${hit.inci_name}`}>
                {hit.summary} — listed {ordinal(hit.position)} of {ingredients.length}
                {hit.prominent ? ', so present at a meaningful level' : ''}
              </Typography>
            ))}
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            {COVERAGE_CAVEAT}
          </Typography>
        </Alert>
      )}

      {allergens && hits.length === 0 && (
        <Alert
          severity={allergens.verdict === 'incomplete' ? 'info' : 'success'}
          variant="outlined"
          icon={
            allergens.verdict === 'incomplete' ? undefined : (
              <CheckCircleOutlineIcon fontSize="inherit" />
            )
          }
        >
          None of the ingredients you avoid appear in this list.
          {allergens.unknown_count > 0 &&
            ` ${allergens.unknown_count} of ${ingredients.length} ingredients here aren't in our
             database, so we could not check those.`}
          {allergens.unrecognized.length > 0 &&
            ` We don't recognise ${formatList(allergens.unrecognized)}, so we searched for that
             wording exactly as you typed it.`}{' '}
          {COVERAGE_CAVEAT}
        </Alert>
      )}

      {analysis.active_groups.length > 0 && (
        <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap alignItems="center">
          <ScienceIcon sx={{ fontSize: 18, color: 'primary.main' }} />
          <Typography variant="body2" color="text.secondary" sx={{ mr: 0.5 }}>
            Actives:
          </Typography>
          {analysis.active_groups.map((group) => (
            <Chip
              key={group}
              label={ACTIVE_GROUP_LABELS[group] ?? group}
              size="small"
              color="primary"
              variant="outlined"
            />
          ))}
        </Stack>
      )}

      {flags.length > 0 && (
        <Alert
          severity="warning"
          variant="outlined"
          icon={<WarningAmberIcon fontSize="inherit" />}
        >
          {flags.join(' · ')}
        </Alert>
      )}

      <ProvenanceBreakdown ingredients={ingredients} analysis={analysis} />

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
          Listed in INCI order — ingredients near the top are present at the highest
          concentrations.
        </Typography>

        <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
          {ingredients.map((ingredient) => {
            const label = ingredient.common_name ?? ingredient.inci_name
            const detail = [
              ingredient.function,
              ingredient.source ? SOURCE_LABELS[ingredient.source] : null,
              ingredient.comedogenic_rating
                ? `comedogenic ${ingredient.comedogenic_rating}/5`
                : null,
              ingredient.description,
            ]
              .filter(Boolean)
              .join(' — ')

            return (
              <Tooltip key={`${ingredient.position}-${ingredient.inci_name}`} title={detail || ''}>
                <Chip
                  label={label}
                  size="small"
                  variant={
                    flaggedNames.has(ingredient.inci_name) || ingredient.is_active
                      ? 'filled'
                      : 'outlined'
                  }
                  color={
                    flaggedNames.has(ingredient.inci_name)
                      ? 'error'
                      : ingredient.is_active
                        ? 'primary'
                        : ingredient.is_irritant
                          ? 'warning'
                          : 'default'
                  }
                  sx={{
                    opacity:
                      flaggedNames.has(ingredient.inci_name) ||
                      ingredient.is_prominent ||
                      ingredient.is_active
                        ? 1
                        : 0.72,
                    borderStyle: ingredient.known ? 'solid' : 'dashed',
                  }}
                />
              </Tooltip>
            )
          })}
        </Stack>

        {analysis.unknown_count > 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
            {analysis.unknown_count} ingredient{analysis.unknown_count === 1 ? '' : 's'} not in our
            database (shown with a dashed border).
          </Typography>
        )}
      </Paper>

      <Box>
        <Typography variant="caption" color="text.secondary">
          Filled chips are actives · amber are common irritants
          {hits.length > 0 ? ' · red are ingredients you avoid' : ''} · hover any ingredient
          for detail.
        </Typography>
      </Box>
    </Stack>
  )
}
