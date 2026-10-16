import React from 'react'
import { act, render, screen } from '@testing-library/react'
import LoginPage from './page'
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, USER_KEY, clearAuthCookie } from '@/lib/auth-storage'

const mockPush = jest.fn()
let mockAfterSignIn: (user: { id?: string } | null) => void
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: mockPush }), useSearchParams: () => new URLSearchParams('switch_account=1&redirect=%2Fprofile') }))
jest.mock('@/lib/janua-client', () => ({ januaClient: {} }))
jest.mock('@/lib/auth-storage', () => ({ ...jest.requireActual('@/lib/auth-storage'), clearAuthCookie: jest.fn() }))
jest.mock('@janua/ui', () => ({
  SignIn: ({ afterSignIn }: { afterSignIn: typeof mockAfterSignIn }) => {
    mockAfterSignIn = afterSignIn
    return <div>Fresh credential and MFA form</div>
  },
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardDescription: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardTitle: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

it('keeps the active RP credentials on account-switch entry and offers a nonmutating cancel', () => {
  localStorage.setItem(ACCESS_TOKEN_KEY, 'synthetic-current-access')
  localStorage.setItem(REFRESH_TOKEN_KEY, 'synthetic-current-refresh')
  localStorage.setItem(USER_KEY, JSON.stringify({ id: 'fixture-current', roles: ['viewer'] }))
  render(<LoginPage />)
  expect(screen.getByRole('heading', { name: 'Switch Janua account' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /cancel and return/i })).toHaveAttribute('href', '/profile')
  expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe('synthetic-current-access')
  expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe('synthetic-current-refresh')
  expect(JSON.parse(localStorage.getItem(USER_KEY)!)).toEqual({ id: 'fixture-current', roles: ['viewer'] })
  expect(clearAuthCookie).not.toHaveBeenCalled()
  expect(mockPush).not.toHaveBeenCalled()
})

it('rejects incomplete fresh identity proof before the sign-in component can redirect', () => {
  localStorage.setItem(ACCESS_TOKEN_KEY, 'synthetic-current-access')
  localStorage.setItem(USER_KEY, JSON.stringify({ id: 'fixture-current', roles: ['viewer'] }))
  render(<LoginPage />)
  act(() => {
    expect(() => mockAfterSignIn(null)).toThrow('Complete sign-in before switching accounts.')
  })
  expect(localStorage.getItem(USER_KEY)).toBe(JSON.stringify({ id: 'fixture-current', roles: ['viewer'] }))
  expect(clearAuthCookie).not.toHaveBeenCalled()
  expect(mockPush).not.toHaveBeenCalled()
})
