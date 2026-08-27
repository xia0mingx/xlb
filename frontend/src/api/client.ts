import type {
  AllergenGroup,
  ChatMessage,
  ChatReply,
  Conflict,
  CurrencyCatalogue,
  Dupe,
  FilterOptions,
  PriceHistory,
  ProductDetail,
  ProductPage,
  ProductSummary,
  QuizOptions,
  QuizResponse,
  SkinProfile,
} from './types'

// Vite proxies /api to the FastAPI server in dev, so this stays relative.
const BASE = '/api'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const body = await response.text().catch(() => '')
    throw new ApiError(response.status, body || response.statusText)
  }
  return response.json() as Promise<T>
}

export interface ProductQuery {
  q?: string
  category?: string
  concern?: string
  brand?: string
  min_price?: number
  max_price?: number
  sort?: string
  page?: number
  page_size?: number
  avoid?: string[]
}

function toQueryString(params: object): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    // Arrays repeat the key rather than joining: INCI names contain commas
    // ("1,2-Hexanediol"), so any delimiter would be ambiguous.
    if (Array.isArray(value)) {
      value.filter(Boolean).forEach((entry) => search.append(key, String(entry)))
      return
    }
    search.set(key, String(value))
  })
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export const api = {
  products: (query: ProductQuery = {}) =>
    request<ProductPage>(`/products${toQueryString(query)}`),

  product: (slug: string, avoid: string[] = []) =>
    request<ProductDetail>(`/products/${slug}${toQueryString({ avoid })}`),

  priceHistory: (slug: string, days = 90) =>
    request<PriceHistory[]>(`/products/${slug}/prices?days=${days}`),

  dupes: (slug: string) => request<Dupe[]>(`/products/${slug}/dupes`),

  deals: (limit = 8, avoid: string[] = []) =>
    request<ProductSummary[]>(`/products/deals${toQueryString({ limit, avoid })}`),

  filters: () => request<FilterOptions>('/products/filters'),

  quizOptions: () => request<QuizOptions>('/quiz/options'),

  allergens: () => request<AllergenGroup[]>('/allergens'),

  recommend: (profile: SkinProfile & { limit?: number }) =>
    request<QuizResponse>('/quiz/recommend', {
      method: 'POST',
      body: JSON.stringify(profile),
    }),

  currencies: (timezone?: string) =>
    request<CurrencyCatalogue>(`/currencies${timezone ? `?timezone=${encodeURIComponent(timezone)}` : ''}`),

  chatStatus: () => request<{ enabled: boolean }>('/chat/status'),

  chat: (body: {
    message: string
    history: ChatMessage[]
    avoid: string[]
    currency?: string
  }) =>
    request<ChatReply>('/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  conflicts: (productIds: number[]) =>
    request<Conflict[]>('/routine/conflicts', {
      method: 'POST',
      body: JSON.stringify({ product_ids: productIds }),
    }),
}

export { ApiError }
