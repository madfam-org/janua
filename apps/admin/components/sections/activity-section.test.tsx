import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { adminAPI, type ActivityLog } from '@/lib/admin-api'
import { ActivitySection } from './activity-section'

jest.mock('@/lib/admin-api', () => ({ adminAPI: { getActivityLogs: jest.fn() } }))
const getLogs = jest.mocked(adminAPI.getActivityLogs)
const event = (id: string, action: string): ActivityLog => ({ id, action, user_id: 'fixture-user', user_email: 'fixture@example.test', ip_address: null, user_agent: null, details: {}, created_at: new Date().toISOString() })

beforeEach(() => jest.clearAllMocks())

it.each([{ logs: [] }, { logs: [event('one', 'logout')] }])('shows unavailable when the sample contains no authentication outcomes %#', async ({ logs }) => {
  getLogs.mockResolvedValue(logs)
  render(<ActivitySection />)
  expect(await screen.findByText('Unavailable')).toBeInTheDocument()
  expect(screen.getByText('No authentication events in the filtered sample.')).toBeInTheDocument()
  expect(screen.queryByText('100.0%')).not.toBeInTheDocument()
  expect(screen.getByText(/filtered latest 50-event sample, not complete period totals/)).toBeInTheDocument()
  expect(screen.getByRole('option', { name: 'Any time in sample' })).toBeInTheDocument()
  expect(getLogs).toHaveBeenCalledWith(50)
})

it('computes measured success for the filtered sample and becomes unavailable when filtering out auth', async () => {
  getLogs.mockResolvedValue([event('one', 'login'), event('two', 'login_success'), event('three', 'login_failed'), event('four', 'logout')])
  render(<ActivitySection />)
  expect(await screen.findByText('66.7%')).toBeInTheDocument()
  expect(screen.getByText('Showing 4 of 4 sampled events')).toBeInTheDocument()
  fireEvent.change(screen.getByRole('combobox', { name: 'Filter by action type' }), { target: { value: 'logout' } })
  expect(screen.getByText('Unavailable')).toBeInTheDocument()
  expect(screen.getByText('Showing 1 of 4 sampled events')).toBeInTheDocument()
})

it('preserves measured zero-percent success', async () => {
  getLogs.mockResolvedValue([event('one', 'login_failed')])
  render(<ActivitySection />)
  expect(await screen.findByText('0.0%')).toBeInTheDocument()
  expect(screen.queryByText('Unavailable')).not.toBeInTheDocument()
})

it('shows stale refresh errors alongside the previous sample and recovers', async () => {
  getLogs.mockResolvedValue([event('one', 'login')])
  render(<ActivitySection />)
  await screen.findByText('100.0%')
  getLogs.mockRejectedValueOnce(new Error('fixture outage'))
  fireEvent.click(screen.getByRole('button', { name: 'Refresh activity logs' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Showing the previously loaded sample; it may be outdated')
  expect(screen.getByText('100.0%')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Refresh activity logs' }))
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
})

it('shows initial request errors with a working retry', async () => {
  getLogs.mockRejectedValueOnce(new Error('fixture outage')).mockResolvedValue([])
  render(<ActivitySection />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Activity logs could not be refreshed')
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText('No authentication events in the filtered sample.')).toBeInTheDocument()
})
