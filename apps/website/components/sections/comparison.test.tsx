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
    expect(screen.getByText('How Janua compares')).toBeInTheDocument()
    expect(screen.getByText('Janua')).toBeInTheDocument()
    expect(screen.getByText('Features')).toBeInTheDocument()
  })

  it('publishes no unmeasured latency or edge-location figures', () => {
    const { container } = render(<ComparisonSection />)
    const text = container.textContent ?? ''
    expect(text).not.toMatch(/Edge Verification|Global Edge PoPs|<30ms|150\+/)
  })
})
