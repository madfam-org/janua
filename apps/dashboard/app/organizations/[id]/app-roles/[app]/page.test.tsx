import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useParams } from 'next/navigation'
import AppRolesAdminPage from './page'
import { grantAppRole, listAppRoleGrants, revokeAppRole } from '@/lib/app-roles-api'

/**
 * The delegated app-role admin page. The API is the authority; these tests pin
 * what the page does with its answers: a refusal is never shown as an empty
 * list, and the caller's own admin grant cannot be revoked from here.
 */

jest.mock('@/lib/app-roles-api', () => {
  const actual = jest.requireActual('@/lib/app-roles-api')
  return {
    ...actual,
    listAppRoleGrants: jest.fn(),
    grantAppRole: jest.fn(),
    revokeAppRole: jest.fn(),
  }
})

const mockList = listAppRoleGrants as jest.MockedFunction<typeof listAppRoleGrants>
const mockGrant = grantAppRole as jest.MockedFunction<typeof grantAppRole>
const mockRevoke = revokeAppRole as jest.MockedFunction<typeof revokeAppRole>

const ORG = '0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0'
const CARO = 'caro-user-id'
const COLLEAGUE = 'colleague-user-id'

function httpError(statusCode: number): Error {
  return Object.assign(new Error('An error occurred'), { statusCode })
}

const listing = {
  organization_id: ORG,
  app: 'creator-census',
  caller_user_id: CARO,
  caller_roles: ['admin'],
  grants: [
    {
      id: 'g1',
      user_id: CARO,
      email: 'caro@example.com',
      name: 'Caro',
      role: 'admin',
      claim_value: 'creator-census:admin',
      granted_by: 'internal-api-key',
      granted_at: '2026-09-25T12:00:00Z',
    },
    {
      id: 'g2',
      user_id: COLLEAGUE,
      email: 'colega@example.com',
      name: null,
      role: 'viewer',
      claim_value: 'creator-census:viewer',
      granted_by: CARO,
      granted_at: '2026-09-25T12:05:00Z',
    },
  ],
  members: [
    { user_id: CARO, email: 'caro@example.com', name: 'Caro' },
    { user_id: COLLEAGUE, email: 'colega@example.com', name: null },
  ],
}

describe('AppRolesAdminPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(useParams as jest.Mock).mockReturnValue({ id: ORG, app: 'creator-census' })
  })

  it('lists live grants and disables revoking the caller’s own admin role', async () => {
    mockList.mockResolvedValue(listing)

    render(<AppRolesAdminPage />)

    await waitFor(() => {
      expect(screen.getByText('creator-census:viewer')).toBeInTheDocument()
    })
    const revokeButtons = screen.getAllByRole('button', { name: /Revoke/ })
    expect(revokeButtons).toHaveLength(2)
    expect(revokeButtons[0]).toBeDisabled() // Caro's own admin grant
    expect(revokeButtons[1]).toBeEnabled()
  })

  it('explains a 403 instead of rendering an empty list', async () => {
    mockList.mockRejectedValue(httpError(403))

    render(<AppRolesAdminPage />)

    await waitFor(() => {
      expect(screen.getByText('You cannot manage this app')).toBeInTheDocument()
    })
    expect(
      screen.getByText(/requires the creator-census:admin role/),
    ).toBeInTheDocument()
    expect(screen.queryByText('No member holds a role in this app.')).not.toBeInTheDocument()
  })

  it('grants a role to the picked member through the API', async () => {
    mockList.mockResolvedValue(listing)
    mockGrant.mockResolvedValue({
      id: 'g3',
      organization_id: ORG,
      user_id: COLLEAGUE,
      app: 'creator-census',
      role: 'editor',
      claim_value: 'creator-census:editor',
      granted_at: '2026-09-25T12:10:00Z',
      revoked_at: null,
      changed: true,
    })

    render(<AppRolesAdminPage />)
    await waitFor(() => expect(screen.getByLabelText('Member')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Member'), { target: { value: COLLEAGUE } })
    fireEvent.change(screen.getByLabelText('Role'), { target: { value: 'editor' } })
    fireEvent.click(screen.getByRole('button', { name: /Grant/ }))

    await waitFor(() => {
      expect(mockGrant).toHaveBeenCalledWith(ORG, 'creator-census', { user_id: COLLEAGUE }, 'editor')
    })
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('Granted creator-census:editor')
    })
  })

  it('does not offer granting admin to oneself', async () => {
    mockList.mockResolvedValue(listing)

    render(<AppRolesAdminPage />)
    await waitFor(() => expect(screen.getByLabelText('Member')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Member'), { target: { value: CARO } })
    fireEvent.change(screen.getByLabelText('Role'), { target: { value: 'admin' } })

    expect(screen.getByRole('button', { name: /Grant/ })).toBeDisabled()
  })

  it('reports the last-admin refusal on revoke', async () => {
    // Another admin, revoked while a concurrent change left them the last one.
    mockList.mockResolvedValue({
      ...listing,
      grants: [
        listing.grants[0],
        { ...listing.grants[1], role: 'admin', claim_value: 'creator-census:admin' },
      ],
    })
    mockRevoke.mockRejectedValue(httpError(409))

    render(<AppRolesAdminPage />)
    await waitFor(() => expect(screen.getAllByRole('button', { name: /Revoke/ })).toHaveLength(2))

    fireEvent.click(screen.getAllByRole('button', { name: /Revoke/ })[1])

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(
        'Refused: this would leave the organization with no admin for this app.',
      )
    })
  })
})
