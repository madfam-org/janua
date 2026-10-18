/**
 * Janua's managed (Pro) price as Dhanam publishes it.
 *
 * Pricing authority: the SKU tiers and prices are authored in the MADFAM SKU
 * catalog and published by Dhanam at `GET /v1/billing/catalog/<product>`
 * (public, no auth). Dhanam's checkout charges the Pro plan in MXN with 16% IVA
 * included, so the pricing page shows that amount from the catalog instead of
 * a figure typed into this repo.
 *
 * The page CSP keeps `connect-src` to 'self', so the catalog is read on the
 * server (the pricing route) and passed to the client section as a prop.
 */

export const JANUA_CATALOG_PRODUCT = 'janua'
export const JANUA_PRO_TIER = 'pro'

/** Revalidate window for the catalog read (seconds). */
export const CATALOG_REVALIDATE_SECONDS = 300

const DEFAULT_CATALOG_BASE = 'https://api.dhan.am/v1/billing/catalog'
const FETCH_TIMEOUT_MS = 5000

/** MXN, whole pesos, IVA included, as the checkout charges them. */
export interface CatalogMxnPrice {
  monthly: number
  yearly: number | null
}

type PriceRow = { monthly?: number | null; yearly?: number | null } | undefined

interface CatalogTier {
  tierSlug?: string
  slug?: string
  prices?: Record<string, PriceRow>
  grossPrices?: Record<string, PriceRow>
}

/** The IVA-inclusive ceil rule Dhanam uses (`ceil_whole_peso_iva`). */
export function mxnGrossFromNetCentavos(netCentavos: number): number {
  return Math.ceil((netCentavos / 100) * 1.16)
}

/** A timeout signal where the runtime has one (Node 18+); none in older test DOMs. */
function timeoutSignal(ms: number): AbortSignal | undefined {
  return typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
    ? AbortSignal.timeout(ms)
    : undefined
}

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function grossPesos(tier: CatalogTier, interval: 'monthly' | 'yearly'): number | null {
  const gross = tier.grossPrices?.MXN?.[interval]
  if (finite(gross)) return Math.round(gross / 100)
  const net = tier.prices?.MXN?.[interval]
  return finite(net) ? mxnGrossFromNetCentavos(net) : null
}

/**
 * The tier's MXN gross price from a catalog product body, or null when the
 * tier or its monthly MXN price is missing.
 */
export function tierMxnPriceFromCatalog(
  product: unknown,
  tierSlug: string = JANUA_PRO_TIER
): CatalogMxnPrice | null {
  const tiers = (product as { tiers?: unknown } | null)?.tiers
  if (!Array.isArray(tiers)) return null
  const tier = (tiers as CatalogTier[]).find(
    (t) => (t?.tierSlug ?? t?.slug) === tierSlug
  )
  if (!tier) return null
  const monthly = grossPesos(tier, 'monthly')
  if (monthly === null) return null
  return { monthly, yearly: grossPesos(tier, 'yearly') }
}

/** `499` → `MX$499`, `4789` → `MX$4,789`. */
export function formatMxnPesos(pesos: number): string {
  return `MX$${pesos.toLocaleString('en-US')}`
}

/**
 * Reads the Pro price from Dhanam's catalog. Never throws: on any failure it
 * logs and returns null, and the page says the MXN amount is shown at
 * checkout instead of showing a stale number.
 */
export async function fetchJanuaProPrice(
  fetchImpl: typeof fetch = fetch
): Promise<CatalogMxnPrice | null> {
  const base = (process.env.DHANAM_CATALOG_URL || DEFAULT_CATALOG_BASE).replace(/\/+$/, '')
  const url = `${base}/${JANUA_CATALOG_PRODUCT}`
  try {
    const res = await fetchImpl(url, {
      next: { revalidate: CATALOG_REVALIDATE_SECONDS },
      signal: timeoutSignal(FETCH_TIMEOUT_MS),
    } as RequestInit)
    if (!res.ok) {
      console.error(`[pricing] Dhanam catalog ${url} answered ${res.status}`)
      return null
    }
    const price = tierMxnPriceFromCatalog(await res.json())
    if (!price) console.error(`[pricing] Dhanam catalog ${url} has no MXN ${JANUA_PRO_TIER} price`)
    return price
  } catch (error) {
    console.error(`[pricing] Dhanam catalog ${url} unreachable`, error)
    return null
  }
}
