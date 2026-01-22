import React from 'react'
import { render, screen } from '@testing-library/react'
import { stats as Stats } from './stats'

describe('stats', () => {
  it('should render without crashing', () => {
    render(<Stats />)
    expect(screen.getByTestId('stats')).toBeInTheDocument()
  })
})
