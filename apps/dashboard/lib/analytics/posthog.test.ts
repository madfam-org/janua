/** @jest-environment node */

const mockPostHog = { init: jest.fn(), capture: jest.fn(), identify: jest.fn(), reset: jest.fn() }
jest.mock('posthog-js', () => ({ __esModule: true, default: mockPostHog }))

const capability = `https://app.janua.dev/invitations/accept?token=${'z'.repeat(43)}`
function location(url: string, referrer = '') {
  Object.defineProperty(global, 'window', { configurable: true, value: { location: new URL(url) } })
  Object.defineProperty(global, 'document', { configurable: true, value: { referrer } })
}
function load() {
  return require('./posthog') as typeof import('./posthog')
}
function beforeSend(event: unknown): unknown {
  return mockPostHog.init.mock.calls[0][1].before_send(event)
}

describe('dashboard invitation capability analytics boundary', () => {
  beforeEach(() => {
    jest.resetModules()
    jest.clearAllMocks()
    process.env.NEXT_PUBLIC_POSTHOG_KEY = 'synthetic-test-key'
    location('https://app.janua.dev/organizations')
  })
  afterAll(() => {
    Reflect.deleteProperty(global, 'window')
    Reflect.deleteProperty(global, 'document')
  })

  it.each([
    capability,
    `https://app.janua.dev/login?${new URLSearchParams({ redirect: '/invitations/accept?token=' + 'z'.repeat(43) })}`,
    `https://app.janua.dev/login?${new URLSearchParams({ redirect: encodeURIComponent('/invitations/accept?token=' + 'z'.repeat(43)) })}`,
  ])('never initializes or sends an initial/manual event on a capability URL', url => {
    location(url)
    const analytics = load()
    analytics.initPostHog()
    analytics.trackEvent('$pageview')
    analytics.identifyUser('synthetic-self')
    expect(mockPostHog.init).not.toHaveBeenCalled()
    expect(mockPostHog.capture).not.toHaveBeenCalled()
    expect(mockPostHog.identify).not.toHaveBeenCalled()
  })

  it('does not initialize when the first unrelated page has an invitation referrer', () => {
    location('https://app.janua.dev/organizations', capability)
    load().initPostHog()
    expect(mockPostHog.init).not.toHaveBeenCalled()
  })

  it('blocks manual/identify and residual automatic events after an initialized SPA enters invitation flow', () => {
    const analytics = load()
    analytics.initPostHog()
    location(capability)
    analytics.trackEvent('$pageview')
    analytics.identifyUser('synthetic-self')
    expect(mockPostHog.capture).not.toHaveBeenCalled()
    expect(mockPostHog.identify).not.toHaveBeenCalled()
    expect(beforeSend({ event: '$autocapture', properties: {} })).toBeNull()
  })

  it.each(['$current_url', '$referrer', '$initial_current_url', '$session_entry_url'])('drops residual attribution carrying %s even on an unrelated current page', key => {
    load().initPostHog()
    expect(beforeSend({ event: '$pageview', properties: { [key]: capability } })).toBeNull()
    expect(beforeSend({ event: '$identify', properties: { $set_once: { [key]: capability } } })).toBeNull()
  })

  it('drops automatic events with encoded login returns and document referrer capabilities', () => {
    load().initPostHog()
    const login = `https://app.janua.dev/login?${new URLSearchParams({ redirect: capability })}`
    expect(beforeSend({ event: '$pageview', properties: { $current_url: login } })).toBeNull()
    location('https://app.janua.dev/organizations', capability)
    expect(beforeSend({ event: '$autocapture', properties: {} })).toBeNull()
  })

  it('preserves unrelated analytics semantics and disabled autocapture/recording configuration', () => {
    const analytics = load()
    analytics.initPostHog()
    const options = mockPostHog.init.mock.calls[0][1]
    expect(options).toMatchObject({ capture_pageview: false, autocapture: false, disable_session_recording: true, respect_dnt: true })
    const event = { event: 'normal', properties: { $current_url: 'https://app.janua.dev/organizations?sort=name', count: 1 } }
    expect(beforeSend(event)).toBe(event)
    const shared = { plan: 'fixture' }
    const alias = { properties: { $set: shared, $set_once: shared } }
    expect(beforeSend(alias)).toBe(alias)
    analytics.trackEvent('normal', { count: 1 })
    analytics.identifyUser('synthetic-self', { plan: 'fixture' })
    analytics.resetUser()
    expect(mockPostHog.capture).toHaveBeenCalledWith('normal', { count: 1 })
    expect(mockPostHog.identify).toHaveBeenCalledWith('synthetic-self', { plan: 'fixture' })
    expect(mockPostHog.reset).toHaveBeenCalledTimes(1)
  })

  it('bounds residual event traversal and fails closed for cycles/oversized capability candidates', () => {
    load().initPostHog()
    const cycle: { child?: unknown } = {}
    cycle.child = cycle
    expect(beforeSend({ properties: cycle })).toBeNull()
    expect(beforeSend({ properties: { url: 'x'.repeat(8193) } })).toBeNull()
  })

  it('is SSR-safe and does not initialize without window', () => {
    Reflect.deleteProperty(global, 'window')
    const analytics = load()
    expect(() => analytics.initPostHog()).not.toThrow()
    analytics.trackEvent('$pageview')
    expect(mockPostHog.init).not.toHaveBeenCalled()
    expect(mockPostHog.capture).not.toHaveBeenCalled()
  })
})
