import React from 'react'
import { render, screen } from '@testing-library/react'
import { ComparisonSection } from './comparison'

describe('ComparisonSection', () => {
  it('should render without crashing', () => {
    render(<ComparisonSection />)
    // Look for typical comparison table headers or content
    const headings = screen.getAllByRole('heading')
    expect(headings.length).toBeGreaterThan(0)
  })

  it('should render comparison content', () => {
    render(<ComparisonSection />)
    // Test that the component renders basic comparison elements
    expect(screen.getByText('Built different. Performs better.')).toBeInTheDocument()
    expect(screen.getByText('Plinto')).toBeInTheDocument()
    expect(screen.getByText('Performance')).toBeInTheDocument()
  })
})
