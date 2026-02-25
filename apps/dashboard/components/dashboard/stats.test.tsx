import React from 'react'
import { render, screen } from '@testing-library/react'
import { DashboardStats } from './stats'

describe('DashboardStats', () => {
  it('should render without crashing', () => {
    render(<DashboardStats />)
    expect(screen.getByTestId('stats')).toBeInTheDocument()
  })
})
