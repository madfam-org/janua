/**
 * Janua publishes no testimonial, logo, adoption figure, uptime figure or
 * service level without a real, consenting customer or a measured figure, and
 * does not claim edge deployment (it runs on MADFAM's own cluster).
 *
 * This scans the source of the rendered marketing pages and sections that
 * once carried such claims, so they do not come back unnoticed.
 */
import { existsSync, readFileSync } from 'fs'
import { join } from 'path'

const ROOT = join(__dirname, '..')

const FILES = [
  'app/(marketing)/solutions/ecommerce/page.tsx',
  'app/(marketing)/solutions/enterprise/page.tsx',
  'app/(marketing)/solutions/healthcare/page.tsx',
  'app/(marketing)/deploy/enclii/page.tsx',
  'components/sections/comparison.tsx',
  'components/sections/pricing.tsx',
  'components/sections/honest-pricing.tsx',
  'components/sections/about.tsx',
]

const BANNED: Array<[string, RegExp]> = [
  ['edge-location count', /\b\d+\+\s*(edge\s+)?locations\b/i],
  ['edge points of presence', /Edge PoPs/i],
  ['edge deployment', /edge deployment/i],
  ['unmeasured latency figure', /[<≤]\s*\d+\s*ms|sub-\d+\s*ms/i],
  ['published uptime percentage', /99\.9+%/],
  ['guaranteed response times', /guaranteed response time/i],
  ['adoption claim', /Fortune 500|trusted by|businesses choose janua/i],
  ['unmeasured outcome figure', /by up to \d+%/i],
  // Janua runs on a single cluster: no multi-region or data-residency offer.
  ['multi-region claim', /multi-region/i],
  ['data residency claim', /data residency/i],
  // No measured savings figure exists. (A billing discount such as
  // "Save 20%" on yearly plans is a price, not a claim, and stays allowed.)
  ['savings percentage', /\d+%\+|cost savings|save \d+%\+?\s*(at scale|vs\b)/i],
  ['unbounded scale claim', /users supported/i],
]

// Unused components that carried simulated edge-latency and edge-location
// figures were deleted; they must not come back.
const DELETED = [
  'components/sections/performance-demo.tsx',
  'components/demo/performance-simulator.tsx',
]

describe('marketing pages carry no unverified claims', () => {
  for (const file of FILES) {
    it(file, () => {
      const source = readFileSync(join(ROOT, file), 'utf8')
      for (const [label, pattern] of BANNED) {
        expect({ label, match: source.match(pattern)?.[0] ?? null }).toEqual({ label, match: null })
      }
    })
  }

  it.each(DELETED)('%s stays deleted', (file) => {
    expect(existsSync(join(ROOT, file))).toBe(false)
  })
})
