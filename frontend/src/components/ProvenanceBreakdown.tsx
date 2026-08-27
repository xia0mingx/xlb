import { Box, Chip, Collapse, Link, Paper, Stack, Tooltip, Typography } from '@mui/material'
import { useState } from 'react'
import type { Ingredient, ProductAnalysis } from '../api/types'

/**
 * Natural / nature-identical / synthetic, as a proportion of the ingredient list.
 *
 * Kept separate from the ingredient chips because those already carry four
 * meanings - active, irritant, avoided, unrecognised - and provenance as a fifth
 * would make none of them legible.
 *
 * Colours are drawn from the chart series palette rather than the semantic
 * red/amber/green, deliberately: origin is not a warning, and colouring
 * "synthetic" like an irritant would editorialise a fact that carries no such
 * meaning.
 */

const BUCKETS = [
  {
    key: 'natural',
    label: 'Natural',
    color: '#8a8f5c',
    description: 'From a plant, mineral or animal source, still recognisably that material.',
  },
  {
    key: 'nature_identical',
    label: 'Nature-identical',
    color: '#5b7fa6',
    description:
      'The same molecule that occurs in nature, but manufactured rather than extracted — chemically indistinguishable.',
  },
  {
    key: 'synthetic',
    label: 'Synthetic',
    color: '#9a7aa0',
    description: 'Made by chemical synthesis, with no natural counterpart.',
  },
  {
    key: 'unknown',
    label: 'Undetermined',
    color: '#b9bdb8',
    description: 'We could not establish an origin. Undisclosed "fragrance" is the usual reason.',
  },
] as const

interface Props {
  ingredients: Ingredient[]
  analysis: ProductAnalysis
}

export function ProvenanceBreakdown({ ingredients, analysis }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)

  const counts: Record<string, number> = {
    natural: analysis.natural_count,
    nature_identical: analysis.nature_identical_count,
    synthetic: analysis.synthetic_count,
    unknown: analysis.unknown_source_count,
  }

  const total = BUCKETS.reduce((sum, bucket) => sum + (counts[bucket.key] ?? 0), 0)
  if (total === 0) return null

  const present = BUCKETS.filter((bucket) => (counts[bucket.key] ?? 0) > 0)

  const namesIn = (key: string) =>
    ingredients
      .filter((i) => (i.source ?? 'unknown') === key)
      .map((i) => i.common_name ?? i.inci_name)

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="baseline"
        sx={{ mb: 1.25 }}
        useFlexGap
        flexWrap="wrap"
      >
        <Typography variant="h6">Ingredient origin</Typography>
        <Typography variant="caption" color="text.secondary">
          Origin only — not a safety or quality ranking
        </Typography>
      </Stack>

      {/* Proportion bar. Each segment is sized by share of the ingredient list. */}
      <Box
        role="img"
        aria-label={present
          .map((b) => `${counts[b.key]} ${b.label.toLowerCase()}`)
          .join(', ')}
        sx={{
          display: 'flex',
          height: 10,
          borderRadius: 5,
          overflow: 'hidden',
          bgcolor: 'action.hover',
          mb: 1.5,
        }}
      >
        {present.map((bucket) => (
          <Tooltip
            key={bucket.key}
            title={`${counts[bucket.key]} of ${total} — ${bucket.label}`}
          >
            <Box
              sx={{
                width: `${((counts[bucket.key] ?? 0) / total) * 100}%`,
                bgcolor: bucket.color,
              }}
            />
          </Tooltip>
        ))}
      </Box>

      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
        {present.map((bucket) => {
          const count = counts[bucket.key] ?? 0
          const share = Math.round((count / total) * 100)
          const isOpen = expanded === bucket.key
          return (
            <Tooltip key={bucket.key} title={bucket.description}>
              <Chip
                size="small"
                variant={isOpen ? 'filled' : 'outlined'}
                onClick={() => setExpanded(isOpen ? null : bucket.key)}
                aria-expanded={isOpen}
                label={
                  <Stack direction="row" spacing={0.75} alignItems="center" component="span">
                    <Box
                      component="span"
                      sx={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        bgcolor: bucket.color,
                        display: 'inline-block',
                      }}
                    />
                    <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {count} {bucket.label.toLowerCase()} · {share}%
                    </span>
                  </Stack>
                }
              />
            </Tooltip>
          )
        })}
      </Stack>

      {present.map((bucket) => (
        <Collapse key={bucket.key} in={expanded === bucket.key} unmountOnExit>
          <Box sx={{ mt: 1.5, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
            <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
              {bucket.description}
            </Typography>
            <Typography variant="body2">{namesIn(bucket.key).join(', ')}</Typography>
          </Box>
        </Collapse>
      ))}

      {!expanded && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.25 }}>
          <Link component="button" type="button" underline="hover" onClick={() => setExpanded(present[0].key)}>
            Show which ingredients
          </Link>
        </Typography>
      )}
    </Paper>
  )
}
