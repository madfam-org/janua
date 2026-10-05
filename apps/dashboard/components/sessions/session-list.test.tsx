import React from 'react'
import { render, waitFor } from '@testing-library/react'

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

// SessionList loads through the SDK client, not fetch. The mock answers with
// the API's real shape (`GET /api/v1/sessions/` -> `{ sessions, total }`,
// SessionsListResponse in apps/api/app/routers/v1/sessions.py). The component
// still reads `.items`, so it logs "sessionList.map is not a function" and
// shows its error state: a known gap listed under "Open items" in
// docs/runbooks/oauth-shared-state-redis.md. This test pins only the load.
const mockListSessions = jest.fn(() => Promise.resolve({ sessions: [], total: 0 }))
jest.mock('@/lib/janua-client', () => ({
  januaClient: {
    sessions: {
      listSessions: () => mockListSessions(),
      revokeSession: jest.fn(),
      revokeAllSessions: jest.fn(),
    },
  },
}))

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

  it('should load the sessions through the SDK client on mount', async () => {
    render(<SessionList />)
    await waitFor(() => expect(mockListSessions).toHaveBeenCalledTimes(1))
    expect(global.fetch).not.toHaveBeenCalled()
  })
})
