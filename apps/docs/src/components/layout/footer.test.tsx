import React from 'react'
import { render, screen } from '@testing-library/react'
import { Footer } from './footer'

// Mock next/link
jest.mock('next/link', () => {
  const MockLink = ({ children, href }: { children: React.ReactNode, href: string }) => (
    <a href={href}>{children}</a>
  )
  MockLink.displayName = 'Link'
  return MockLink
})

describe('Footer', () => {
  it('should render without crashing', () => {
    render(<Footer />)
    expect(screen.getByText('© 2024 Plinto. All rights reserved.')).toBeInTheDocument()
  })
})
