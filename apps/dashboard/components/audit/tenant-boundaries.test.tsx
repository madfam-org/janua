import React from 'react'
import { render, screen } from '@testing-library/react'
import { AuditList } from './audit-list'
import AuditPage from '@/app/audit-logs/page'
import UserDetailPage from '@/app/users/[id]/page'
import SystemSettingsPage from '@/app/settings/system/page'

jest.mock('@/lib/api', () => new Proxy({}, { get: () => { throw new Error('Tenant fallback must not request platform APIs') } }))
jest.mock('@/lib/janua-client', () => new Proxy({}, { get: () => { throw new Error('Tenant fallback must not connect to global audit stream') } }))

it('does not fetch audit records or offer unsupported exports/live streams', () => {
  render(<AuditList />)
  expect(screen.getByText('Organization audit logs are not available yet.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /export|live/i })).not.toBeInTheDocument()
})
it('keeps the direct audit route unavailable rather than opening global records', () => {
  render(<AuditPage />)
  expect(screen.getByText('Organization audit logs are not available yet.')).toBeInTheDocument()
})
it('requires organization context for a direct user-detail route', () => {
  render(<UserDetailPage />)
  expect(screen.getByRole('link', { name: 'Choose an organization' })).toHaveAttribute('href', '/users')
  expect(screen.queryByRole('button', { name: /suspend|delete|unlock/i })).not.toBeInTheDocument()
})
it('hands system-wide controls to the operator console without fetching settings', () => {
  render(<SystemSettingsPage />)
  expect(screen.getByRole('link', { name: 'Open Janua Admin' })).toHaveAttribute('href', 'https://admin.janua.dev')
  expect(screen.getByText(/Organization roles do not grant platform access/)).toBeInTheDocument()
})
