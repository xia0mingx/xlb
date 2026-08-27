import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import { Alert, AlertTitle, Stack, Typography } from '@mui/material'
import type { AllergenScreen } from '../api/types'

export const COVERAGE_CAVEAT =
  'Screening compares your list against the published ingredient list. It cannot account for ' +
  'reformulation, cross-contamination, or "may contain" traces — check the pack if you react severely.'

function ordinal(n: number): string {
  const rem100 = n % 100
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`
  return `${n}${['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'}`
}

interface Props {
  allergens: AllergenScreen | null | undefined
  totalIngredients: number
}

/**
 * The allergen verdict, rendered above the fold on the product page.
 *
 * It used to sit inside the ingredient list, two screens down. If someone is
 * allergic to something in a product, that is the first thing they need to
 * know about it - not the last.
 */
export function AllergenBanner({ allergens, totalIngredients }: Props) {
  const hits = allergens?.hits ?? []
  if (!allergens || hits.length === 0) return null

  // Position approximates concentration, so something listed 3rd matters more
  // than the same thing listed 30th. The highest tier wins for the banner.
  const anyProminent = hits.some((hit) => hit.prominent)

  return (
    <Alert
      severity={anyProminent ? 'error' : 'warning'}
      variant="outlined"
      icon={<ErrorOutlineIcon fontSize="inherit" />}
      sx={{ borderLeftWidth: 3, alignItems: 'flex-start' }}
    >
      <AlertTitle>
        Contains {hits.length} ingredient{hits.length === 1 ? '' : 's'} you avoid
      </AlertTitle>
      <Stack component="ul" spacing={0.25} sx={{ m: 0, pl: 2.5 }}>
        {hits.map((hit) => (
          <Typography component="li" variant="body2" key={`${hit.position}-${hit.inci_name}`}>
            {hit.summary} — listed {ordinal(hit.position)}
            {totalIngredients > 0 ? ` of ${totalIngredients}` : ''}
            {hit.prominent ? ', so present at a meaningful level' : ''}
          </Typography>
        ))}
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
        {COVERAGE_CAVEAT}
      </Typography>
    </Alert>
  )
}
