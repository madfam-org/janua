import React from 'react'
import { render, screen } from '@testing-library/react'
import { page as Page } from './page'

describe('page', () => {
  it('should render without crashing', () => {
    render(<Page />)
    expect(screen.getByTestId('page')).toBeInTheDocument()
  })
})
