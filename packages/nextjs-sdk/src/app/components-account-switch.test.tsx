import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { UserButton } from './components'
import { useAuth } from './provider'

vi.mock('./provider', () => ({ useAuth: vi.fn(), useUser: vi.fn() }))
vi.mock('@janua/ui/components/auth', () => ({
  SignIn: () => null,
  SignUp: () => null,
  UserButton: ({ user, onSwitchAccount }: { user: { email: string }; onSwitchAccount?: () => void }) => <div><span>{user.email}</span>{onSwitchAccount && <button onClick={onSwitchAccount}>Switch account</button>}</div>,
}))

describe('Next.js configured account switching', () => {
  const switchAccount = vi.fn()
  const signOut = vi.fn()
  const registration = { clientId: 'fixture-rp', redirectUri: 'https://rp.example.test/callback' }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue({ auth: { switchAccount }, user: { id: 'fixture-current', email: 'current@example.test' }, signOut } as unknown as ReturnType<typeof useAuth>)
  })
  afterEach(cleanup)

  it('hides the action until a working RP registration is supplied', () => {
    render(<UserButton />)
    expect(screen.queryByRole('button', { name: 'Switch account' })).toBeNull()
  })

  it('starts selection without invoking sign out', async () => {
    switchAccount.mockResolvedValue(undefined)
    render(<UserButton switchAccountOptions={registration} />)
    fireEvent.click(screen.getByRole('button', { name: 'Switch account' }))
    await waitFor(() => expect(switchAccount).toHaveBeenCalledWith(registration))
    expect(signOut).not.toHaveBeenCalled()
  })

  it('preserves the active account after a failed selection start', async () => {
    switchAccount.mockRejectedValue(new Error('Unavailable'))
    render(<UserButton switchAccountOptions={registration} />)
    fireEvent.click(screen.getByRole('button', { name: 'Switch account' }))
    expect((await screen.findByRole('alert')).textContent).toContain('current session is unchanged')
    expect(screen.getByText('current@example.test')).not.toBeNull()
    expect(signOut).not.toHaveBeenCalled()
  })
})
