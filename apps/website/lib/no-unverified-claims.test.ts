/**
 * Janua publishes no testimonial, logo, adoption figure, uptime figure or
 * service level without a real, consenting customer or a measured figure, and
 * does not claim edge deployment (it runs on MADFAM's own cluster).
 *
 * This scans the source of the rendered marketing pages and sections that
 * once carried such claims, so they do not come back unnoticed.
 */
import { readFileSync } from 'fs'
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
})
