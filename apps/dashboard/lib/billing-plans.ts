/**
 * Plans sold through a conversation, not a checkout.
 *
 * Dhanam's catalog sells janua only as `pro` (plus the free `open_source`).
 * A "scale" checkout used to resolve, through the webhook's legacy plan map,
 * to `dhanam_pro`, so it would have sold a Dhanam plan to a Janua buyer.
 * janua.dev has no MX record, so the old `mailto:sales@janua.dev` could not
 * receive mail either. Both plans go to the MADFAM discovery-call booking (the
 * same fallback Dhanam's hosted checkout uses), tagged with the product.
 */
export const SALES_CONTACT_URL = 'https://kalya.app/madfam?product=janua'

const CONTACT_SALES_PLAN_IDS: ReadonlySet<string> = new Set(['scale', 'enterprise'])

export function isContactSalesPlan(planId: string): boolean {
  return CONTACT_SALES_PLAN_IDS.has(planId)
}
