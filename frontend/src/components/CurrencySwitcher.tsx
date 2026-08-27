import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { Button, ListItemText, Menu, MenuItem, Tooltip, Typography } from '@mui/material'
import { useRef, useState } from 'react'
import { useCurrency } from '../currency'

/**
 * Switches the display currency.
 *
 * The default comes from the viewer's time zone, so most people never touch
 * this. It exists because detection is a guess - somebody travelling, or on a
 * VPN, or simply wanting to compare in dollars, should be able to override it,
 * and the choice then sticks.
 */
export function CurrencySwitcher() {
  const { currency, options, setCurrency, chosen, note } = useCurrency()
  const anchorRef = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)

  if (options.length < 2) return null

  const tooltip = chosen
    ? `Showing ${currency.name}`
    : `Showing ${currency.name}, based on your region`

  return (
    <>
      <Tooltip title={tooltip}>
        <Button
          ref={anchorRef}
          color="inherit"
          size="small"
          onClick={() => setOpen(true)}
          endIcon={<ExpandMoreIcon />}
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label={`Change currency. ${tooltip}`}
          sx={{ minWidth: 0 }}
        >
          <Typography component="span" sx={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
            {currency.symbol} {currency.code}
          </Typography>
        </Button>
      </Tooltip>

      <Menu
        anchorEl={anchorRef.current}
        open={open}
        onClose={() => setOpen(false)}
        slotProps={{ paper: { sx: { minWidth: 232 } } }}
      >
        {options.map((option) => (
          <MenuItem
            key={option.code}
            selected={option.code === currency.code}
            onClick={() => {
              setCurrency(option.code)
              setOpen(false)
            }}
          >
            <ListItemText
              primary={`${option.symbol} ${option.code}`}
              secondary={option.name}
            />
          </MenuItem>
        ))}

        {note && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', px: 2, pt: 1, pb: 0.5, maxWidth: 232 }}
          >
            {note}
          </Typography>
        )}
      </Menu>
    </>
  )
}
