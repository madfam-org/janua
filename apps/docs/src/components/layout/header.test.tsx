import React from 'react'
import { render } from '@testing-library/react'
import { Header } from './header'

// Mock next/navigation
jest.mock('next/navigation', () => ({
  usePathname: () => '/getting-started',
  useRouter: () => ({
    push: jest.fn(),
  }),
}))

// Mock next/link
jest.mock('next/link', () => {
  const MockLink = ({ children, href }: { children: React.ReactNode, href: string }) => (
    <a href={href}>{children}</a>
  )
  MockLink.displayName = 'Link'
  return MockLink
})

// Mock next-themes
jest.mock('next-themes', () => ({
  useTheme: () => ({
    theme: 'light',
    setTheme: jest.fn(),
  }),
}))

describe('Header', () => {
  it('should render without crashing', () => {
    render(<Header />)
  })
})
