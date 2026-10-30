import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useRouter } from 'next/navigation'
import ProfilePage from './page'

jest.mock('@/lib/janua-client', () => ({
  januaClient: {
    auth: { getCurrentUser: jest.fn() },
    sessions: { listSessions: jest.fn() },
    signOut: jest.fn(),
  },
}))
jest.mock('@/lib/api', () => ({
  updateProfile: jest.fn(), changePassword: jest.fn(), enableMfa: jest.fn(),
  verifyMfa: jest.fn(), disableMfa: jest.fn(), listPasskeys: jest.fn(),
  deletePasskey: jest.fn(), registerPasskey: jest.fn(), listDevices: jest.fn(),
  trustDevice: jest.fn(), revokeDevice: jest.fn(),
}))
jest.mock('@/lib/auth-storage', () => ({ clearAuthCookie: jest.fn() }))
jest.mock('next/navigation', () => ({ useRouter: jest.fn() }))

const { januaClient } = jest.requireMock('@/lib/janua-client')
const { disableMfa, listPasskeys } = jest.requireMock('@/lib/api')
const { clearAuthCookie } = jest.requireMock('@/lib/auth-storage')
const replace = jest.fn()

async function openDisableForm() {
  render(<ProfilePage />)
  const security = await screen.findByRole('tab', { name: 'Security' })
  fireEvent.mouseDown(security, { button: 0, ctrlKey: false })
  fireEvent.click(security)
  fireEvent.click(await screen.findByRole('button', { name: 'Disable MFA', exact: true }))
  return {
    password: screen.getByLabelText('Current password'),
    code: screen.getByLabelText('Authenticator or backup code'),
    submit: screen.getByRole('button', { name: 'Disable MFA and sign out' }),
  }
}

beforeEach(() => {
  jest.clearAllMocks()
  ;(useRouter as jest.Mock).mockReturnValue({ replace })
  januaClient.auth.getCurrentUser.mockResolvedValue({
    id: 'synthetic-user', email: 'member@example.invalid', mfa_enabled: true,
  })
  januaClient.sessions.listSessions.mockResolvedValue({ sessions: [], total: 0 })
  januaClient.signOut.mockResolvedValue(undefined)
  disableMfa.mockResolvedValue({ message: 'MFA disabled' })
  listPasskeys.mockResolvedValue([])
})

describe('MFA disable confirmation', () => {
  it('requires both secrets before calling the existing disable endpoint', async () => {
    const form = await openDisableForm()
    expect(form.password).toHaveAttribute('type', 'password')
    expect(form.code).toHaveAttribute('type', 'password')
    expect(form.submit).toBeDisabled()
    fireEvent.change(form.password, { target: { value: 'Synthetic-Password-7!' } })
    expect(form.submit).toBeDisabled()
    expect(disableMfa).not.toHaveBeenCalled()
  })

  it.each(['123456', 'unused-backup-code'])('submits a %s code and retires the revoked session', async code => {
    const form = await openDisableForm()
    fireEvent.change(form.password, { target: { value: 'Synthetic-Password-7!' } })
    fireEvent.change(form.code, { target: { value: code } })
    fireEvent.click(form.submit)
    await waitFor(() => expect(disableMfa).toHaveBeenCalledWith({
      password: 'Synthetic-Password-7!', code,
    }))
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login?reason=mfa_disabled'))
    expect(januaClient.signOut).toHaveBeenCalledTimes(1)
    expect(clearAuthCookie).toHaveBeenCalledTimes(1)
    expect(screen.queryByLabelText('Current password')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Authenticator or backup code')).not.toBeInTheDocument()
  })

  it('clears inputs after rejection without echoing remote error text or signing out', async () => {
    disableMfa.mockRejectedValueOnce(new Error('private remote response'))
    const form = await openDisableForm()
    fireEvent.change(form.password, { target: { value: 'Synthetic-Password-7!' } })
    fireEvent.change(form.code, { target: { value: '123456' } })
    fireEvent.click(form.submit)
    await screen.findByText(/Could not disable MFA/)
    expect(screen.getByRole('alert')).toHaveTextContent(/Could not disable MFA/)
    expect(form.password).toHaveValue('')
    expect(form.code).toHaveValue('')
    expect(screen.queryByText('private remote response')).not.toBeInTheDocument()
    expect(januaClient.signOut).not.toHaveBeenCalled()
    expect(replace).not.toHaveBeenCalled()
  })

  it('clears secrets on cancel and does not submit a code', async () => {
    const form = await openDisableForm()
    fireEvent.change(form.password, { target: { value: 'Synthetic-Password-7!' } })
    fireEvent.change(form.code, { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel', exact: true }))
    fireEvent.click(screen.getByRole('button', { name: 'Disable MFA', exact: true }))
    expect(screen.getByLabelText('Current password')).toHaveValue('')
    expect(screen.getByLabelText('Authenticator or backup code')).toHaveValue('')
    expect(disableMfa).not.toHaveBeenCalled()
  })

  it('still clears the cookie and goes to sign-in if SDK sign-out fails', async () => {
    januaClient.signOut.mockRejectedValueOnce(new Error('already revoked'))
    const form = await openDisableForm()
    fireEvent.change(form.password, { target: { value: 'Synthetic-Password-7!' } })
    fireEvent.change(form.code, { target: { value: '123456' } })
    fireEvent.click(form.submit)
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login?reason=mfa_disabled'))
    expect(clearAuthCookie).toHaveBeenCalledTimes(1)
  })
})
