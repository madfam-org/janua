import {
  fetchJanuaProPrice,
  formatMxnPesos,
  mxnGrossFromNetCentavos,
  tierMxnPriceFromCatalog,
} from './dhanam-catalog'

// Shape of GET https://api.dhan.am/v1/billing/catalog/janua (2026-10-18).
const catalogJanua = {
  slug: 'janua',
  tiers: [
    { tierSlug: 'open_source', slug: 'open_source', prices: {}, grossPrices: {} },
    {
      tierSlug: 'pro',
      slug: 'pro',
      prices: {
        USD: { monthly: 2900, yearly: 27840 },
        MXN: { monthly: 43000, yearly: 412800 },
      },
      grossPrices: {
        MXN: { monthly: 49900, yearly: 478900, ivaRate: 0.16, pricingRule: 'ceil_whole_peso_iva' },
      },
    },
  ],
}

describe('dhanam catalog: Janua Pro price', () => {
  it('reads the IVA-inclusive MXN gross the checkout charges', () => {
    expect(tierMxnPriceFromCatalog(catalogJanua)).toEqual({ monthly: 499, yearly: 4789 })
  })

  it('derives the gross with the ceil rule when the catalog sends only the net', () => {
    const netOnly = {
      tiers: [{ tierSlug: 'pro', prices: { MXN: { monthly: 43000, yearly: 412800 } } }],
    }
    expect(mxnGrossFromNetCentavos(43000)).toBe(499)
    expect(tierMxnPriceFromCatalog(netOnly)).toEqual({ monthly: 499, yearly: 4789 })
  })

  it('returns null when the tier or its MXN price is missing', () => {
    expect(tierMxnPriceFromCatalog({ tiers: [] })).toBeNull()
    expect(tierMxnPriceFromCatalog({ tiers: [{ tierSlug: 'pro', prices: {} }] })).toBeNull()
    expect(tierMxnPriceFromCatalog(null)).toBeNull()
  })

  it('formats whole pesos', () => {
    expect(formatMxnPesos(499)).toBe('MX$499')
    expect(formatMxnPesos(4789)).toBe('MX$4,789')
  })

  it('fetches the janua product and never throws', async () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {})
    const ok = jest.fn().mockResolvedValue({ ok: true, json: async () => catalogJanua })
    await expect(fetchJanuaProPrice(ok as unknown as typeof fetch)).resolves.toEqual({
      monthly: 499,
      yearly: 4789,
    })
    expect(ok.mock.calls[0][0]).toBe('https://api.dhan.am/v1/billing/catalog/janua')

    const notFound = jest.fn().mockResolvedValue({ ok: false, status: 503 })
    await expect(fetchJanuaProPrice(notFound as unknown as typeof fetch)).resolves.toBeNull()

    const down = jest.fn().mockRejectedValue(new Error('ECONNREFUSED'))
    await expect(fetchJanuaProPrice(down as unknown as typeof fetch)).resolves.toBeNull()
    expect(errorSpy).toHaveBeenCalled()
    errorSpy.mockRestore()
  })
})
