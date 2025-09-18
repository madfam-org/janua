import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { Providers } from '@/components/providers'

// Mock @plinto/react-sdk
jest.mock('@plinto/react-sdk', () => ({
  PlintoProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}))

// Mock hooks
jest.mock('@/hooks/useEnvironment', () => ({
  useEnvironment: () => ({
    environment: {
      apiUrl: 'http://localhost:4000',
      publicUrl: 'http://localhost:3000'
    },
    mounted: true
  })
}))

// Mock PlintoClient
jest.mock('@plinto/typescript-sdk', () => ({
  PlintoClient: jest.fn().mockImplementation(() => ({
    initialize: jest.fn()
  }))
}))

describe('Providers', () => {
  it('should render children', async () => {
    render(
      <Providers>
        <div data-testid="test-child">Test Child</div>
      </Providers>
    )
    
    await waitFor(() => {
      expect(screen.getByTestId('test-child')).toBeInTheDocument()
    })
  })
})
