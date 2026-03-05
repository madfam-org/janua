import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createApp, inject } from 'vue'
import { createJanua, JANUA_KEY, JanuaVue } from '../plugin'

vi.mock('@janua/typescript-sdk', () => {
  const mockAuth = {
    signIn: vi.fn().mockResolvedValue({ access_token: 'tok' }),
    signUp: vi.fn().mockResolvedValue({ id: '1' }),
    signOut: vi.fn().mockResolvedValue(undefined),
    getCurrentUser: vi.fn().mockResolvedValue(null),
    handleOAuthCallback: vi.fn().mockResolvedValue(undefined),
    sendMagicLink: vi.fn().mockResolvedValue(undefined),
    verifyMagicLink: vi.fn().mockResolvedValue(undefined),
    enableMFA: vi.fn().mockResolvedValue({ secret: 'abc' }),
    verifyMFA: vi.fn().mockResolvedValue({ access_token: 'tok' }),
    disableMFA: vi.fn().mockResolvedValue(undefined),
    getPasskeyRegistrationOptions: vi.fn().mockResolvedValue({}),
    getPasskeyAuthenticationOptions: vi.fn().mockResolvedValue({}),
  }
  return {
    JanuaClient: vi.fn().mockImplementation(() => ({
      auth: mockAuth,
      users: { updateCurrentUser: vi.fn() },
      organizations: {},
      getCurrentUser: vi.fn().mockResolvedValue(null),
      getAccessToken: vi.fn().mockResolvedValue(null),
      getRefreshToken: vi.fn().mockResolvedValue(null),
      signOut: vi.fn().mockResolvedValue(undefined),
      signInWithPasskey: vi.fn().mockResolvedValue(undefined),
      registerPasskey: vi.fn().mockResolvedValue(undefined),
      updateUser: vi.fn().mockResolvedValue(undefined),
    })),
    checkWebAuthnSupport: vi.fn().mockReturnValue({
      available: true,
      platform: false,
      conditional: false,
    }),
  }
})

const BASE_URL = 'http://localhost:4100'

describe('JanuaVue Plugin', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('installs and provides JanuaVue via JANUA_KEY', () => {
    const app = createApp({ render: () => null })
    const plugin = createJanua({ baseURL: BASE_URL })
    app.use(plugin)

    let janua: JanuaVue | undefined
    app.runWithContext(() => {
      janua = inject<JanuaVue>(JANUA_KEY)
    })

    expect(janua).toBeInstanceOf(JanuaVue)
  })

  it('destroy clears the polling interval', async () => {
    const clearSpy = vi.spyOn(globalThis, 'clearInterval')
    const janua = new JanuaVue({ baseURL: BASE_URL })

    // Let the initialize() microtask and interval setup complete
    await vi.advanceTimersByTimeAsync(0)

    janua.destroy()
    expect(clearSpy).toHaveBeenCalled()
  })

  it('SSR safety: initialize does not throw when window is undefined', () => {
    const originalWindow = globalThis.window
    // @ts-expect-error simulate SSR
    delete globalThis.window

    expect(() => new JanuaVue({ baseURL: BASE_URL })).not.toThrow()

    globalThis.window = originalWindow
  })

  it('error state: errors during signIn populate state.error', async () => {
    const { JanuaClient } = await import('@janua/typescript-sdk')
    const mockInstance = new JanuaClient({} as any)
    ;(mockInstance.auth.signIn as any).mockRejectedValueOnce(new Error('bad creds'))

    const janua = new JanuaVue({ baseURL: BASE_URL })
    await vi.advanceTimersByTimeAsync(0)

    await expect(janua.signIn('a@b.com', 'wrong')).rejects.toThrow('bad creds')
    expect(janua.getState().error?.message).toBe('bad creds')
  })

  it('auth state updates: signIn updates user/session/isAuthenticated', async () => {
    const { JanuaClient } = await import('@janua/typescript-sdk')
    const mockInstance = new JanuaClient({} as any)
    const fakeUser = { id: '1', email: 'a@b.com' }
    ;(mockInstance.getCurrentUser as any).mockResolvedValue(fakeUser)
    ;(mockInstance.getAccessToken as any).mockResolvedValue('access-tok')
    ;(mockInstance.getRefreshToken as any).mockResolvedValue('refresh-tok')

    const janua = new JanuaVue({ baseURL: BASE_URL })
    await vi.advanceTimersByTimeAsync(0)

    await janua.signIn('a@b.com', 'pass')

    expect(janua.getState().isAuthenticated).toBe(true)
    expect(janua.getState().user).toEqual(fakeUser)
    expect(janua.getState().session).toBeTruthy()
  })

  it('app.unmount() calls janua.destroy()', async () => {
    const app = createApp({ render: () => null })
    const plugin = createJanua({ baseURL: BASE_URL })
    app.use(plugin)
    app.mount(document.createElement('div'))

    const destroySpy = vi.spyOn(JanuaVue.prototype, 'destroy')
    app.unmount()

    expect(destroySpy).toHaveBeenCalled()
    destroySpy.mockRestore()
  })
})
