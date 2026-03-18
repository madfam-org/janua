import React from 'react'
import { render } from '@testing-library/react'
import { UserProfile } from './UserProfile'

jest.mock('../provider', () => ({
  ...jest.requireActual('../provider'),
  useJanua: () => ({
    user: { id: 'test', email: 'test@example.com', name: 'Test User' },
    session: null,
    isLoading: false,
    error: null,
    signOut: jest.fn(),
  }),
}))

describe('UserProfile', () => {
  it('should render without crashing', () => {
    const { container } = render(<UserProfile />)
    expect(container.firstChild).toBeTruthy()
  })
})
