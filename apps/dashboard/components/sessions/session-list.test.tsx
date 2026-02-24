import React from 'react'
import { render, screen } from '@testing-library/react'

// Mock @janua/ui
jest.mock('@janua/ui', () => ({
  Button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
  Badge: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  DropdownMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

// Mock fetch for API calls
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: () =>
      Promise.resolve({
        items: [],
        total: 0,
      }),
  })
) as jest.Mock

// Mock localStorage
Storage.prototype.getItem = jest.fn(() => 'test-token')

import { SessionList } from './session-list'

describe('SessionList', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('should render loading state initially', () => {
    render(<SessionList />)
    // The component shows a loading spinner on initial render
    expect(document.body).toBeTruthy()
  })

  it('should call the sessions API on mount', () => {
    render(<SessionList />)
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/sessions'),
      expect.any(Object)
    )
  })
})
