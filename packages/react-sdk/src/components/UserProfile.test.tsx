import React from 'react'
import { render, screen } from '@testing-library/react'
import { UserProfile } from './UserProfile'

describe('UserProfile', () => {
  it('should render without crashing', () => {
    render(<UserProfile />)
    expect(screen.getByTestId('UserProfile')).toBeInTheDocument()
  })
})
