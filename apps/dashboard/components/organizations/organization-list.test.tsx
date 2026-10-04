import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { OrganizationList } from './organization-list'
import { getAccountOrganizations } from '@/lib/organization-directory-api'

jest.mock('@/lib/organization-directory-api', () => ({ getAccountOrganizations: jest.fn() }))
const getOrganizations = jest.mocked(getAccountOrganizations)
beforeEach(() => getOrganizations.mockReset())
it('shows membership data without invented plan or account status', async () => {
  getOrganizations.mockResolvedValue([{ id: 'org-a', name: 'Example organization', slug: 'example', memberCount: null }])
  render(<OrganizationList />)
  expect(await screen.findByRole('link', { name: 'Example organization' })).toHaveAttribute('href', '/organizations/org-a')
  expect(screen.getByText('Unavailable')).toBeInTheDocument()
  expect(screen.queryByRole('columnheader', { name: 'Plan' })).not.toBeInTheDocument()
  expect(screen.queryByRole('columnheader', { name: 'Status' })).not.toBeInTheDocument()
})
it('distinguishes errors from no memberships and permits retry', async () => {
  getOrganizations.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce([])
  render(<OrganizationList />)
  expect(await screen.findByText('Your organizations are unavailable.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('No organizations are associated with your account.')).toBeInTheDocument()
})
