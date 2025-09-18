import React from 'react'
import { render, screen } from '@testing-library/react'
import { provider } from './provider'

describe('provider', () => {
  it('should render without crashing', () => {
    render(<provider />)
    expect(screen.getByTestId('provider')).toBeInTheDocument()
  })
})
