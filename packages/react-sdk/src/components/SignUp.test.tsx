import React from 'react'
import { render, screen } from '@testing-library/react'
import { SignUp } from './SignUp'

describe('SignUp', () => {
  it('should render without crashing', () => {
    render(<SignUp />)
    expect(screen.getByTestId('SignUp')).toBeInTheDocument()
  })
})
