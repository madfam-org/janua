import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { RecentActivity } from './recent-activity'
import { getPersonalSessionActivity } from '@/lib/dashboard-api'

jest.mock('@/lib/dashboard-api', () => ({ getPersonalSessionActivity: jest.fn() }))
const getActivity = jest.mocked(getPersonalSessionActivity)
beforeEach(() => { getActivity.mockReset() })

it('shows only personal session descriptions and explicit missing timestamps', async () => {
  getActivity.mockResolvedValue([{ id: 'session-a', action: 'Session started', timestamp: null, device: 'Example browser', revoked: true }])
  render(<RecentActivity />)
  expect(await screen.findByRole('list', { name: 'Your recent session activity' })).toBeInTheDocument()
  expect(screen.getByText('Session started · Revoked session')).toBeInTheDocument()
  expect(screen.getByText('Example browser')).toBeInTheDocument()
  expect(screen.getByText('Time unavailable')).toBeInTheDocument()
})
it('shows an empty state only for a successful empty response', async () => {
  getActivity.mockResolvedValue([])
  render(<RecentActivity />)
  expect(await screen.findByText('No recent session activity for your account.')).toBeInTheDocument()
})
it('shows unavailable on errors and retries without claiming history is empty', async () => {
  getActivity.mockRejectedValueOnce(new Error('upstream unavailable')).mockResolvedValueOnce([])
  render(<RecentActivity />)
  expect(await screen.findByText('Your session activity is currently unavailable.')).toBeInTheDocument()
  expect(screen.queryByText('No recent session activity for your account.')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('No recent session activity for your account.')).toBeInTheDocument()
})
