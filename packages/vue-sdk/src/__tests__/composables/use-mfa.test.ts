import { describe, it, expect, vi } from 'vitest'
import { useMFA } from '../../composables'
import { withSetup } from '../helpers'

const mockEnableMFA = vi.fn().mockResolvedValue({ secret: 'totp-secret', qr_uri: 'otpauth://...' })
const mockVerifyMFA = vi.fn().mockResolvedValue({ access_token: 'new-tok' })
const mockDisableMFA = vi.fn().mockResolvedValue(undefined)

vi.mock('@janua/typescript-sdk', () => ({
  JanuaClient: vi.fn().mockImplementation(() => ({
    auth: {
      signIn: vi.fn(),
      signUp: vi.fn(),
      signOut: vi.fn(),
      getCurrentUser: vi.fn().mockResolvedValue(null),
      handleOAuthCallback: vi.fn(),
      sendMagicLink: vi.fn(),
      verifyMagicLink: vi.fn(),
      enableMFA: mockEnableMFA,
      verifyMFA: mockVerifyMFA,
      disableMFA: mockDisableMFA,
    },
    users: { updateCurrentUser: vi.fn() },
    organizations: {},
    getCurrentUser: vi.fn().mockResolvedValue(null),
    getAccessToken: vi.fn().mockResolvedValue(null),
    getRefreshToken: vi.fn().mockResolvedValue(null),
    signOut: vi.fn().mockResolvedValue(undefined),
    signInWithPasskey: vi.fn(),
    registerPasskey: vi.fn(),
  })),
  checkWebAuthnSupport: vi.fn().mockReturnValue({ available: true, platform: false, conditional: false }),
}))

describe('useMFA', () => {
  it('enableMFA calls client.auth.enableMFA with type', async () => {
    const { result } = withSetup(() => useMFA())

    const res = await result.enableMFA('totp')
    expect(mockEnableMFA).toHaveBeenCalledWith('totp')
    expect(res).toEqual({ secret: 'totp-secret', qr_uri: 'otpauth://...' })
  })

  it('verifyMFA calls client.auth.verifyMFA and returns tokens', async () => {
    const { result } = withSetup(() => useMFA())

    const res = await result.verifyMFA('123456')
    expect(mockVerifyMFA).toHaveBeenCalledWith({ code: '123456' })
    expect(res).toEqual({ access_token: 'new-tok' })
  })

  it('disableMFA calls client.auth.disableMFA', async () => {
    const { result } = withSetup(() => useMFA())

    await result.disableMFA('mypassword')
    expect(mockDisableMFA).toHaveBeenCalledWith('mypassword')
  })

  it('error handling sets error ref and manages isLoading', async () => {
    mockEnableMFA.mockRejectedValueOnce(new Error('mfa setup failed'))
    const { result } = withSetup(() => useMFA())

    await expect(result.enableMFA('totp')).rejects.toThrow('mfa setup failed')
    expect(result.error.value?.message).toBe('mfa setup failed')
    expect(result.isLoading.value).toBe(false)
  })
})
