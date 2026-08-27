export const CATEGORY_LABELS: Record<string, string> = {
  cleanser: 'Cleanser',
  toner: 'Toner',
  essence: 'Essence',
  serum: 'Serum',
  moisturizer: 'Moisturizer',
  sunscreen: 'Sunscreen',
  mask: 'Mask',
  eye_cream: 'Eye Cream',
  exfoliant: 'Exfoliant',
  treatment: 'Treatment',
}

export const ACTIVE_GROUP_LABELS: Record<string, string> = {
  retinoid: 'Retinoid',
  aha: 'AHA',
  bha: 'BHA',
  pha: 'PHA',
  vitamin_c: 'Vitamin C',
  niacinamide: 'Niacinamide',
  azelaic: 'Azelaic acid',
  benzoyl_peroxide: 'Benzoyl peroxide',
  brightener: 'Brightening',
  peptide: 'Peptide',
  antioxidant: 'Antioxidant',
  soothing: 'Soothing',
  uv_filter: 'UV filter',
  bakuchiol: 'Bakuchiol',
  sulfur: 'Sulfur',
}

/**
 * Price per millilitre or gram.
 *
 * The headline number is not comparable across sizes - $46.40 for 100ml and
 * $30.00 for 150ml only rank correctly once both are per-unit. Returns null for
 * countable units (sheets, patches), where a per-unit price is meaningless.
 */
const COUNTABLE_UNITS = new Set(['ea', 'pc', 'pcs', 'sheet', 'sheets', 'patch', 'patches'])

export function formatUnitPrice(
  price: number | null | undefined,
  size: number | null | undefined,
  unit: string | null | undefined,
  convert: (value: number) => number = (value) => value,
  symbol = '$',
): string | null {
  if (price === null || price === undefined) return null
  if (!size || size <= 0 || !unit) return null
  if (COUNTABLE_UNITS.has(unit.toLowerCase())) return null
  const per = convert(price / size)
  // Sub-cent values need more precision or a cheap large-volume product reads
  // as "$0.00/ml", which is worse than showing nothing.
  return `${symbol}${per < 0.01 ? per.toFixed(4) : per.toFixed(2)}/${unit}`
}

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `$${value.toFixed(2)}`
}

export function formatRelativeTime(iso: string | null): string {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'unknown'

  const minutes = Math.round((Date.now() - then) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  return `${days}d ago`
}

/** Distinct, theme-consistent colours for each retailer line on the chart. */
export const SERIES_COLORS = ['#3f6f5f', '#b4674f', '#5b7fa6', '#9a7aa0', '#8a8f5c', '#c08a3e']
