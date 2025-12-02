import { render, screen } from '@testing-library/react'
import { PricingSection } from './pricing'

describe('PricingSection', () => {
  it('should render without crashing', () => {
    render(<PricingSection />)
    expect(screen.getByText('Simple, transparent pricing')).toBeInTheDocument()
  })

  it('should display all pricing plans', () => {
    render(<PricingSection />)
    expect(screen.getByText('Community')).toBeInTheDocument()
    expect(screen.getByText('Pro')).toBeInTheDocument()
    expect(screen.getByText('Scale')).toBeInTheDocument()
    expect(screen.getByText('Enterprise')).toBeInTheDocument()
  })

  it('should show annual/monthly toggle', () => {
    render(<PricingSection />)
    expect(screen.getByText('Monthly')).toBeInTheDocument()
    expect(screen.getByText('Annual')).toBeInTheDocument()
    expect(screen.getByText('Save 15%')).toBeInTheDocument()
  })

  it('should display FAQ section', () => {
    render(<PricingSection />)
    expect(screen.getByText('Frequently Asked Questions')).toBeInTheDocument()
    expect(screen.getByText('What counts as a Monthly Active User (MAU)?')).toBeInTheDocument()
  })
})