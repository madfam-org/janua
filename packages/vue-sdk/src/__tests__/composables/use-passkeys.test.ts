import { describe, it, expect, vi } from 'vitest'
import { usePasskeys } from '../../composables'
import { withSetup } from '../helpers'

const mockRegisterPasskey = vi.fn().mockResolvedValue(undefined)
const mockSignInWithPasskey = vi.fn().mockResolvedValue(undefined)

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
      enableMFA: vi.fn(),
      verifyMFA: vi.fn(),
      disableMFA: vi.fn(),
    },
    users: { updateCurrentUser: vi.fn() },
    organizations: {},
    getCurrentUser: vi.fn().mockResolvedValue(null),
    getAccessToken: vi.fn().mockResolvedValue(null),
    getRefreshToken: vi.fn().mockResolvedValue(null),
    signOut: vi.fn().mockResolvedValue(undefined),
    signInWithPasskey: mockSignInWithPasskey,
    registerPasskey: mockRegisterPasskey,
  })),
  checkWebAuthnSupport: vi.fn().mockReturnValue({ available: true, platform: false, conditional: false }),
}))

describe('usePasskeys', () => {
  it('isSupported reflects WebAuthn availability', () => {
    const { result } = withSetup(() => usePasskeys())
    expect(result.isSupported.value).toBe(true)
  })

  it('registerPasskey calls client.registerPasskey()', async () => {
    const { result } = withSetup(() => usePasskeys())

    await result.registerPasskey('my-key')
    expect(mockRegisterPasskey).toHaveBeenCalledWith('my-key')
  })

  it('authenticateWithPasskey calls client.signInWithPasskey()', async () => {
    const { result } = withSetup(() => usePasskeys())

    await result.authenticateWithPasskey('user@test.com')
    expect(mockSignInWithPasskey).toHaveBeenCalledWith('user@test.com')
  })

  it('error handling sets error ref on failure', async () => {
    mockRegisterPasskey.mockRejectedValueOnce(new Error('webauthn failed'))
    const { result } = withSetup(() => usePasskeys())

    await expect(result.registerPasskey()).rejects.toThrow('webauthn failed')
    expect(result.error.value?.message).toBe('webauthn failed')
  })
})
