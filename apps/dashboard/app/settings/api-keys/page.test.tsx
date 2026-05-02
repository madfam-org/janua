import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import ApiKeysPage from './page'

jest.mock('@/lib/api', () => ({
  listApiKeys: jest.fn(),
  createApiKey: jest.fn(),
  revokeApiKey: jest.fn(),
}))

const { listApiKeys } = jest.requireMock('@/lib/api')

describe('ApiKeysPage error/empty XOR', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('shows error state and NOT empty state when fetch fails (e.g. 503)', async () => {
    listApiKeys.mockRejectedValueOnce(new Error('Request failed with status code 503'))

    render(<ApiKeysPage />)

    await waitFor(() => {
      expect(screen.getByTestId('api-keys-error')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('api-keys-empty')).not.toBeInTheDocument()
    expect(screen.queryByText(/no api keys yet/i)).not.toBeInTheDocument()
    expect(screen.getByText(/could not load api keys/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('shows empty state and NOT error state when fetch succeeds with []', async () => {
    listApiKeys.mockResolvedValueOnce([])

    render(<ApiKeysPage />)

    await waitFor(() => {
      expect(screen.getByTestId('api-keys-empty')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('api-keys-error')).not.toBeInTheDocument()
    expect(screen.getByText(/no api keys yet/i)).toBeInTheDocument()
  })
})
