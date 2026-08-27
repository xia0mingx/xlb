import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import ScienceIcon from '@mui/icons-material/Science'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import {
  Alert,
  Box,
  Chip,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material'
import type { AllergenScreen, Ingredient, ProductAnalysis } from '../api/types'
import { COVERAGE_CAVEAT } from './AllergenBanner'
import { ACTIVE_GROUP_LABELS } from '../format'
import { ProvenanceBreakdown } from './ProvenanceBreakdown'

// Kept: the provenance labels upstream added. Dropped: COVERAGE_CAVEAT and
// ordinal(), which moved to AllergenBanner along with the warning that used them.
const SOURCE_LABELS: Record<string, string> = {
  natural: 'natural',
  nature_identical: 'nature-identical',
  synthetic: 'synthetic',
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

  const flags: string[] = []
  if (analysis.has_fragrance) flags.push('Contains fragrance')
  if (analysis.has_alcohol) flags.push('Contains denatured alcohol')
  if (analysis.has_essential_oil) flags.push('Contains essential oils')
  if (analysis.max_comedogenic >= 3) {
    flags.push(`Comedogenic ingredient rated ${analysis.max_comedogenic}/5`)
  }

  return (
    <Stack spacing={2}>
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
          {hits.length > 0 ? ' · red are ingredients you avoid' : ''} · dimmed sit past the
          first eight positions and are likely present in small amounts · hover any ingredient
          for detail.
        </Typography>
      </Box>
    </Stack>
  )
}
