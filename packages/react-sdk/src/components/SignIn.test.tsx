import React from 'react'
import { render, screen } from '@testing-library/react'
import { SignIn } from './SignIn'

describe('SignIn', () => {
  it('should render without crashing', () => {
    render(<SignIn />)
    expect(screen.getByTestId('SignIn')).toBeInTheDocument()
  })
})
