import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { UserButton } from './UserButton'
import { useJanua } from '../provider'

jest.mock('../provider', () => ({ useJanua: jest.fn() }))
jest.mock('@janua/ui/components/auth', () => ({
  UserButton: ({ user, onSwitchAccount }: any) => <div><span>{user.email}</span>{onSwitchAccount && <button onClick={onSwitchAccount}>Switch account</button>}</div>,
}))

describe('configured account switching', () => {
  const switchAccount = jest.fn()
  const signOut = jest.fn()
  const registration = { clientId: 'fixture-rp', redirectUri: 'https://rp.example.test/callback' }

  beforeEach(() => {
    jest.clearAllMocks()
    ;(useJanua as jest.Mock).mockReturnValue({ user: { id: 'fixture-current', email: 'current@example.test' }, client: { auth: { switchAccount } }, signOut })
  })

  it('does not display a nonfunctional unconfigured switch action', () => {
    render(<UserButton />)
    expect(screen.queryByRole('button', { name: 'Switch account' })).not.toBeInTheDocument()
  })

  it('passes the RP registration to the hosted chooser without signing out', async () => {
    switchAccount.mockResolvedValue(undefined)
    render(<UserButton switchAccountOptions={registration} />)
    fireEvent.click(screen.getByRole('button', { name: 'Switch account' }))
    await waitFor(() => expect(switchAccount).toHaveBeenCalledWith(registration))
    expect(signOut).not.toHaveBeenCalled()
    expect(screen.getByText('current@example.test')).toBeInTheDocument()
  })

  it('retains the active user and reports a failed selection start', async () => {
    switchAccount.mockRejectedValue(new Error('Unavailable'))
    render(<UserButton switchAccountOptions={registration} />)
    fireEvent.click(screen.getByRole('button', { name: 'Switch account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('current session is unchanged')
    expect(screen.getByText('current@example.test')).toBeInTheDocument()
    expect(signOut).not.toHaveBeenCalled()
  })
})
