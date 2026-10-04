import React from 'react'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { UsersDataTable } from './users-data-table'
import { getAccountOrganizations, getOrganizationMembers, type OrganizationMember } from '@/lib/organization-directory-api'

jest.mock('@/lib/organization-directory-api', () => ({ getAccountOrganizations: jest.fn(), getOrganizationMembers: jest.fn() }))
const getOrganizations = jest.mocked(getAccountOrganizations)
const getMembers = jest.mocked(getOrganizationMembers)
const member = (id: string): OrganizationMember => ({ id, role: 'member', status: 'active', joinedAt: null, isServiceAccount: false })
beforeEach(() => {
  jest.resetAllMocks()
  getOrganizations.mockResolvedValue([{ id: 'org-a', name: 'Organization A', slug: 'a', memberCount: 1 }, { id: 'org-b', name: 'Organization B', slug: 'b', memberCount: 1 }])
})
it('requires explicit organization selection and shows only organization member data', async () => {
  getMembers.mockResolvedValue([member('member-a')])
  render(<UsersDataTable />)
  const picker = await screen.findByRole('combobox', { name: 'Organization' })
  expect(getMembers).not.toHaveBeenCalled()
  fireEvent.change(picker, { target: { value: 'org-a' } })
  expect(await screen.findByText('member-a')).toBeInTheDocument()
  expect(getMembers).toHaveBeenCalledWith('org-a')
  expect(screen.queryByRole('columnheader', { name: 'MFA' })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Manage organization membership' })).toHaveAttribute('href', '/organizations/org-a?tab=members')
})
it('discards a previous organization response after switching organizations', async () => {
  let resolveA!: (members: OrganizationMember[]) => void
  getMembers.mockImplementationOnce(() => new Promise(resolve => { resolveA = resolve })).mockResolvedValueOnce([member('member-b')])
  render(<UsersDataTable />)
  const picker = await screen.findByRole('combobox', { name: 'Organization' })
  fireEvent.change(picker, { target: { value: 'org-a' } })
  fireEvent.change(picker, { target: { value: 'org-b' } })
  expect(await screen.findByText('member-b')).toBeInTheDocument()
  await act(async () => resolveA([member('member-a')]))
  expect(screen.queryByText('member-a')).not.toBeInTheDocument()
  expect(screen.getByText('member-b')).toBeInTheDocument()
  fireEvent.change(picker, { target: { value: '' } })
  expect(screen.queryByText('member-b')).not.toBeInTheDocument()
})
it('clears previous members before an access failure and offers scoped retry', async () => {
  getMembers.mockResolvedValueOnce([member('member-a')]).mockRejectedValueOnce(new Error('denied')).mockResolvedValueOnce([])
  render(<UsersDataTable />)
  const picker = await screen.findByRole('combobox', { name: 'Organization' })
  fireEvent.change(picker, { target: { value: 'org-a' } })
  await screen.findByText('member-a')
  fireEvent.change(picker, { target: { value: 'org-b' } })
  expect(screen.queryByText('member-a')).not.toBeInTheDocument()
  expect(await screen.findByText('Members of this organization are unavailable or access was denied.')).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('No members were returned for this organization.')).toBeInTheDocument()
  expect(getMembers).toHaveBeenLastCalledWith('org-b')
})
