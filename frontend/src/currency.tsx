import { useQuery } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from './api/client'
import * as storage from './storage'
import type { CurrencyCatalogue, CurrencyInfo } from './api/types'

const STORAGE_NAME = 'currency'

/** Shown before the catalogue loads, so prices never render as bare numbers. */
const FALLBACK: CurrencyInfo = { code: 'USD', symbol: '$', name: 'US dollar', rate: 1 }

interface CurrencyContextValue {
  currency: CurrencyInfo
  options: CurrencyInfo[]
  /** True while we are still deciding, so callers can avoid a flash of the wrong currency. */
  loading: boolean
  /** Null until the viewer picks one explicitly; region detection is not a choice. */
  chosen: string | null
  setCurrency: (code: string) => void
  /** Converts a stored USD amount and renders it with the symbol. */
  formatPrice: (value: number | null | undefined) => string
  /** Converts without formatting — for chart axes that format themselves. */
  convert: (value: number) => number
  note: string | null
}

const CurrencyContext = createContext<CurrencyContextValue | null>(null)

/** The viewer's IANA zone, e.g. Asia/Singapore. Needs no permission prompt. */
function detectTimezone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined
  } catch {
    return undefined
  }
}

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [chosen, setChosen] = useState<string | null>(() => storage.read(STORAGE_NAME))
  const timezone = useMemo(detectTimezone, [])

  // The backend owns the region-to-currency rule and the rates, so the eurozone
  // list is not duplicated here and there is one place to correct it.
  const { data, isLoading } = useQuery<CurrencyCatalogue>({
    queryKey: ['currencies', timezone],
    queryFn: () => api.currencies(timezone),
    staleTime: 60 * 60 * 1000,
  })

  const options = data?.currencies ?? [FALLBACK]

  // An explicit choice always wins; otherwise take the region's suggestion.
  const activeCode = chosen ?? data?.suggested ?? FALLBACK.code
  const currency = options.find((c) => c.code === activeCode) ?? FALLBACK

  const setCurrency = useCallback((code: string) => {
    setChosen(code)
    storage.write(STORAGE_NAME, code)
  }, [])

  useEffect(() => {
    // Keep tabs in step if the currency is switched in another one.
    const onStorage = (event: StorageEvent) => {
      if (storage.eventMatches(event.key, STORAGE_NAME)) setChosen(event.newValue)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const value = useMemo<CurrencyContextValue>(() => {
    const convert = (amount: number) => Math.round(amount * currency.rate * 100) / 100
    return {
      currency,
      options,
      loading: isLoading,
      chosen,
      setCurrency,
      convert,
      formatPrice: (amount) =>
        amount === null || amount === undefined
          ? '—'
          : `${currency.symbol}${convert(amount).toFixed(2)}`,
      note: data?.note ?? null,
    }
  }, [currency, options, isLoading, chosen, setCurrency, data?.note])

  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>
}

export function useCurrency(): CurrencyContextValue {
  const context = useContext(CurrencyContext)
  if (context === null) {
    throw new Error('useCurrency must be used inside a CurrencyProvider')
  }
  return context
}
