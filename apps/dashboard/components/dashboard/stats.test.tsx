import React from 'react'
import { render, screen, within, fireEvent } from '@testing-library/react'
import { DashboardStats } from './stats'
import { getPersonalDashboardStats } from '@/lib/dashboard-api'

jest.mock('@/lib/dashboard-api', () => ({ getPersonalDashboardStats: jest.fn() }))
const getStats = jest.mocked(getPersonalDashboardStats)
beforeEach(() => { getStats.mockReset() })

it('renders real personal counts without platform totals or invented monthly trends', async () => {
  getStats.mockResolvedValue({ organizations: 2, activeSessions: 3 })
  render(<DashboardStats />)
  const overview = screen.getByRole('region', { name: 'Your account overview' })
  expect(await within(overview).findByText('2')).toBeInTheDocument()
  expect(within(overview).getByText('3')).toBeInTheDocument()
  expect(screen.getByText('Your organizations')).toBeInTheDocument()
  expect(screen.getByText('Your active sessions')).toBeInTheDocument()
  expect(screen.queryByText('Total Identities')).not.toBeInTheDocument()
  expect(screen.queryByText(/from last month/)).not.toBeInTheDocument()
  expect(screen.getByText(/Organization-wide.*not available/)).toBeInTheDocument()
})
it('distinguishes missing data from actual zero and allows retry', async () => {
  getStats.mockResolvedValueOnce({ organizations: null, activeSessions: 0 }).mockResolvedValueOnce({ organizations: 4, activeSessions: 0 })
  render(<DashboardStats />)
  expect(await screen.findByText('Unavailable')).toBeInTheDocument()
  expect(screen.getByText('0')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('4')).toBeInTheDocument()
  expect(screen.queryByText('Unavailable')).not.toBeInTheDocument()
})
