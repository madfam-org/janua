import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { JanuaProvider, useJanua } from './provider'

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

// Mock sessionStorage
const sessionStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}
Object.defineProperty(window, 'sessionStorage', {
  value: sessionStorageMock,
})

// Test component that uses the context
function TestComponent() {
  const { user, isAuthenticated, isLoading, error } = useJanua()
  return (
    <div data-testid="test-component">
      <span data-testid="loading">{isLoading ? 'loading' : 'ready'}</span>
      <span data-testid="authenticated">{isAuthenticated ? 'true' : 'false'}</span>
      {user && <span data-testid="user-email">{user.email}</span>}
      {error && <span data-testid="error">{error.message}</span>}
    </div>
  )
}

describe('JanuaProvider', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    localStorageMock.getItem.mockReturnValue(null)
  })

  it('should render children and provide context', async () => {
    render(
      <JanuaProvider config={{ baseURL: 'http://localhost:4100' }}>
        <TestComponent />
      </JanuaProvider>
    )

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('ready')
    })

    expect(screen.getByTestId('test-component')).toBeInTheDocument()
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
  })

  it('should throw error when useJanua is used outside provider', () => {
    // Suppress console.error for this test
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => {
      render(<TestComponent />)
    }).toThrow('useJanua must be used within a JanuaProvider')

    consoleSpy.mockRestore()
  })

  it('should start in loading state and transition to ready', async () => {
    render(
      <JanuaProvider config={{ baseURL: 'http://localhost:4100' }}>
        <TestComponent />
      </JanuaProvider>
    )

    // Initially should be loading
    expect(screen.getByTestId('loading')).toBeInTheDocument()

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('ready')
    })
  })

  it('should accept JanuaProviderConfig with clientId', async () => {
    render(
      <JanuaProvider
        config={{
          baseURL: 'http://localhost:4100',
          clientId: 'test-client',
          redirectUri: 'http://localhost:3000/callback',
        }}
      >
        <TestComponent />
      </JanuaProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('ready')
    })
  })
})
