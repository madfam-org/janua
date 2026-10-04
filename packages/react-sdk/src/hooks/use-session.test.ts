import { act, renderHook } from '@testing-library/react'
import { useSession } from './use-session'

const mockClient = { getRefreshToken: jest.fn(), auth: { refreshToken: jest.fn() } }
jest.mock('../provider', () => ({ useJanua: () => ({ client: mockClient, session: null }) }))
beforeEach(() => { jest.clearAllMocks(); localStorage.clear(); mockClient.getRefreshToken.mockResolvedValue('fixture-refresh') })

it('leaves accepted token persistence to the SDK coordinator', async () => {
  const tokens = { access_token: 'fixture-access', refresh_token: 'fixture-rotated' }
  mockClient.auth.refreshToken.mockResolvedValue(tokens)
  const { result } = renderHook(() => useSession())
  let response: unknown
  await act(async () => { response = await result.current.refreshTokens() })
  expect(response).toEqual(tokens)
  expect(mockClient.auth.refreshToken).toHaveBeenCalledWith()
  expect(localStorage.getItem('janua_access_token')).toBeNull()
})

it('does not delete replacement account credentials when an old refresh fails', async () => {
  mockClient.auth.refreshToken.mockRejectedValue(new Error('fixture superseded refresh'))
  localStorage.setItem('janua_access_token', 'fixture-account-b')
  localStorage.setItem('janua_refresh_token', 'fixture-account-b-refresh')
  const { result } = renderHook(() => useSession())
  await act(async () => { expect(await result.current.refreshTokens()).toBeNull() })
  expect(localStorage.getItem('janua_access_token')).toBe('fixture-account-b')
  expect(localStorage.getItem('janua_refresh_token')).toBe('fixture-account-b-refresh')
})
