import { fireEvent, render, screen } from '@testing-library/react'
import { PricingSection, mxnChargeNote } from './pricing'

describe('PricingSection', () => {
  it('should render without crashing', () => {
    render(<PricingSection />)
    expect(screen.getByText('Simple, transparent pricing')).toBeInTheDocument()
  })

  it('should display all pricing plans', () => {
    render(<PricingSection />)
    expect(screen.getByText('Community')).toBeInTheDocument()
    expect(screen.getByText('Pro')).toBeInTheDocument()
    expect(screen.getByText('Business')).toBeInTheDocument()
    expect(screen.getByText('Enterprise')).toBeInTheDocument()
  })

  it('should show the ratified Managed (Pro) $29 price', () => {
    render(<PricingSection />)
    expect(screen.getAllByText('$29').length).toBeGreaterThan(0)
  })

  it('should not show the retired $69 / $299 prices', () => {
    render(<PricingSection />)
    expect(screen.queryByText('$69')).not.toBeInTheDocument()
    expect(screen.queryByText('$299')).not.toBeInTheDocument()
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

  it('shows the MXN amount the checkout charges, from the catalog', () => {
    render(<PricingSection proMxn={{ monthly: 499, yearly: 4789 }} />)
    expect(screen.getByTestId('pro-mxn-charge')).toHaveTextContent(
      'Charged MX$499/month in MXN, IVA incluido.'
    )
  })

  it('shows the yearly MXN amount on the annual toggle', () => {
    render(<PricingSection proMxn={{ monthly: 499, yearly: 4789 }} />)
    fireEvent.click(screen.getByText('Monthly').nextElementSibling as HTMLElement)
    expect(screen.getByTestId('pro-mxn-charge')).toHaveTextContent(
      'Charged MX$4,789/year in MXN, IVA incluido.'
    )
  })

  it('names no MXN figure when the catalog could not be read', () => {
    render(<PricingSection />)
    expect(screen.getByTestId('pro-mxn-charge')).toHaveTextContent(
      'Charged in MXN with IVA at checkout.'
    )
    expect(mxnChargeNote(null, true)).toBe('Charged in MXN with IVA at checkout.')
  })
})
