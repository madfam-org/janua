import React from 'react'
import { render, screen } from '@testing-library/react'
import DocsHomePage from './page'

// Mock next/link
jest.mock('next/link', () => {
  const MockLink = ({ children, href }: { children: React.ReactNode, href: string }) => (
    <a href={href}>{children}</a>
  )
  MockLink.displayName = 'Link'
  return MockLink
})

describe('DocsHomePage', () => {
  it('should render the main heading', () => {
    render(<DocsHomePage />)
    expect(screen.getByText('Plinto Documentation')).toBeInTheDocument()
  })

  it('should render the description', () => {
    render(<DocsHomePage />)
    expect(screen.getByText(/Everything you need to integrate secure identity management/)).toBeInTheDocument()
  })

  it('should render quick links section', () => {
    render(<DocsHomePage />)
    expect(screen.getByText('Quick Links')).toBeInTheDocument()
    expect(screen.getByText('Quick Start')).toBeInTheDocument()
    expect(screen.getByText('Authentication')).toBeInTheDocument()
    expect(screen.getByText('SDKs')).toBeInTheDocument()
  })

  it('should render popular guides section', () => {
    render(<DocsHomePage />)
    expect(screen.getByText('Popular Guides')).toBeInTheDocument()
    expect(screen.getByText('Implementing Passkeys/WebAuthn')).toBeInTheDocument()
    expect(screen.getByText('Session Management')).toBeInTheDocument()
  })

  it('should render code example', () => {
    render(<DocsHomePage />)
    expect(screen.getByText('Quick Example')).toBeInTheDocument()
    expect(screen.getByText(/import { Plinto }/)).toBeInTheDocument()
  })

  it('should render latest updates', () => {
    render(<DocsHomePage />)
    expect(screen.getByText('Latest Updates')).toBeInTheDocument()
    expect(screen.getByText('Enhanced Passkey Support')).toBeInTheDocument()
    expect(screen.getByText('v1.2.0')).toBeInTheDocument()
  })
})