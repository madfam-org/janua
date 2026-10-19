import { SALES_CONTACT_URL, isContactSalesPlan } from './billing-plans'

describe('billing plans sold through a conversation', () => {
  it('routes Scale and Enterprise to sales, never to a checkout', () => {
    expect(isContactSalesPlan('scale')).toBe(true)
    expect(isContactSalesPlan('enterprise')).toBe(true)
  })

  it('keeps Pro (the only priced janua tier in the catalog) on the checkout', () => {
    expect(isContactSalesPlan('pro')).toBe(false)
    expect(isContactSalesPlan('community')).toBe(false)
  })

  it('sends sales contact to the discovery-call booking, not a janua.dev mailbox', () => {
    const url = new URL(SALES_CONTACT_URL)
    expect(url.protocol).toBe('https:')
    expect(url.hostname).toBe('kalya.app')
    expect(url.pathname).toBe('/madfam')
    expect(url.searchParams.get('product')).toBe('janua')
  })
})
