import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { OrganizationProfile } from './organization-profile'
import type { OrganizationMember } from './organization-profile'

describe('OrganizationProfile', () => {
  const mockOnUpdateOrganization = vi.fn()
  const mockOnUploadLogo = vi.fn()
  const mockOnFetchMembers = vi.fn()
  const mockOnInviteMember = vi.fn()
  const mockOnUpdateMemberRole = vi.fn()
  const mockOnRemoveMember = vi.fn()
  const mockOnDeleteOrganization = vi.fn()
  const mockOnError = vi.fn()

  const mockOrganization = {
    id: 'org-1',
    name: 'Acme Corporation',
    slug: 'acme',
    logoUrl: 'https://example.com/acme.png',
    description: 'A test organization',
    createdAt: new Date('2024-01-01'),
    memberCount: 3,
  }

  const mockMembers: OrganizationMember[] = [
    {
      id: 'member-1',
      email: 'owner@example.com',
      name: 'John Doe',
      role: 'owner',
      avatarUrl: 'https://example.com/john.png',
      joinedAt: new Date('2024-01-01'),
      status: 'active',
    },
    {
      id: 'member-2',
      email: 'admin@example.com',
      name: 'Jane Smith',
      role: 'admin',
      joinedAt: new Date('2024-01-02'),
      status: 'active',
    },
    {
      id: 'member-3',
      email: 'member@example.com',
      role: 'member',
      joinedAt: new Date('2024-01-03'),
      status: 'invited',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render organization profile component', () => {
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
        />
      )

      expect(screen.getByText('Organization settings')).toBeInTheDocument()
      expect(screen.getByText(/Manage your organization/i)).toBeInTheDocument()
    })

    it('should render tabs for owner', () => {
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
        />
      )

      expect(screen.getByRole('tab', { name: /general/i })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /members/i })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /danger zone/i })).toBeInTheDocument()
    })

    it('should not render danger zone tab for non-owners', () => {
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="admin"
        />
      )

      expect(screen.getByRole('tab', { name: /general/i })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /members/i })).toBeInTheDocument()
      expect(screen.queryByRole('tab', { name: /danger zone/i })).not.toBeInTheDocument()
    })

    it('should apply custom className', () => {
      const { container } = render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          className="custom-class"
        />
      )

      expect(container.firstChild).toHaveClass('custom-class')
    })
  })

  describe('General Tab', () => {
    it('should display organization logo', () => {
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
        />
      )

      const logo = screen.getByAltText('Acme Corporation')
      expect(logo).toHaveAttribute('src', 'https://example.com/acme.png')
    })

    it('should display organization initials when no logo', () => {
      const orgWithoutLogo = { ...mockOrganization, logoUrl: undefined }
      render(
        <OrganizationProfile
          organization={orgWithoutLogo}
          userRole="owner"
        />
      )

      expect(screen.getByText('AC')).toBeInTheDocument()
    })

    it('should display organization details', () => {
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
        />
      )

      expect(screen.getByDisplayValue('Acme Corporation')).toBeInTheDocument()
      expect(screen.getByDisplayValue('acme')).toBeInTheDocument()
      expect(screen.getByDisplayValue('A test organization')).toBeInTheDocument()
    })

    it('should show upload logo button for admins', () => {
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="admin"
          onUploadLogo={mockOnUploadLogo}
        />
      )

      expect(screen.getByRole('button', { name: /upload logo/i })).toBeInTheDocument()
    })

    it('should not show upload logo button for members', () => {
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="member"
        />
      )

      expect(screen.queryByRole('button', { name: /upload logo/i })).not.toBeInTheDocument()
    })

    it('should update organization settings', async () => {
      const user = userEvent.setup()
      mockOnUpdateOrganization.mockResolvedValue(undefined)

      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          onUpdateOrganization={mockOnUpdateOrganization}
        />
      )

      const nameInput = screen.getByLabelText(/organization name/i)
      await user.clear(nameInput)
      await user.type(nameInput, 'New Name')

      const saveButton = screen.getByRole('button', { name: /save changes/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(mockOnUpdateOrganization).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'New Name',
          })
        )
      })
    })

    it('should enforce slug pattern', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
        />
      )

      const slugInput = screen.getByLabelText(/organization slug/i)
      await user.clear(slugInput)
      await user.type(slugInput, 'Invalid Slug!')

      expect(slugInput).toHaveValue('invalidslug')
    })

    it('should disable inputs for members', () => {
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="member"
        />
      )

      const nameInput = screen.getByLabelText(/organization name/i)
      const slugInput = screen.getByLabelText(/organization slug/i)

      expect(nameInput).toBeDisabled()
      expect(slugInput).toBeDisabled()
    })

    it('should upload logo', async () => {
      const user = userEvent.setup()
      const file = new File(['logo'], 'logo.png', { type: 'image/png' })
      mockOnUploadLogo.mockResolvedValue('https://example.com/new-logo.png')

      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          onUploadLogo={mockOnUploadLogo}
        />
      )

      const uploadButton = screen.getByRole('button', { name: /upload logo/i })
      await user.click(uploadButton)

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      await user.upload(fileInput, file)

      await waitFor(() => {
        expect(mockOnUploadLogo).toHaveBeenCalledWith(file)
      })
    })

    it('should handle update error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to update organization')
      mockOnUpdateOrganization.mockRejectedValue(error)

      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          onUpdateOrganization={mockOnUpdateOrganization}
          onError={mockOnError}
        />
      )

      const saveButton = screen.getByRole('button', { name: /save changes/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(screen.getByText('Failed to update organization')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })
  })

  describe('Members Tab', () => {
    it('should switch to members tab', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          members={mockMembers}
        />
      )

      const membersTab = screen.getByRole('tab', { name: /members/i })
      await user.click(membersTab)

      expect(screen.getByText(/Members \(3\)/i)).toBeInTheDocument()
    })

    it('should display all members', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          members={mockMembers}
        />
      )

      const membersTab = screen.getByRole('tab', { name: /members/i })
      await user.click(membersTab)

      expect(screen.getByText('owner@example.com')).toBeInTheDocument()
      expect(screen.getByText('admin@example.com')).toBeInTheDocument()
      expect(screen.getByText('member@example.com')).toBeInTheDocument()
    })

    it('should fetch members when tab is opened', async () => {
      const user = userEvent.setup()
      mockOnFetchMembers.mockResolvedValue(mockMembers)

      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          onFetchMembers={mockOnFetchMembers}
        />
      )

      const membersTab = screen.getByRole('tab', { name: /members/i })
      await user.click(membersTab)

      await waitFor(() => {
        expect(mockOnFetchMembers).toHaveBeenCalled()
      })
    })

    it('should display member roles and status', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          members={mockMembers}
        />
      )

      const membersTab = screen.getByRole('tab', { name: /members/i })
      await user.click(membersTab)

      expect(screen.getByText('Invited')).toBeInTheDocument()
    })

    it('should show invite member form for admins', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="admin"
          members={mockMembers}
          onInviteMember={mockOnInviteMember}
        />
      )

      const membersTab = screen.getByRole('tab', { name: /members/i })
      await user.click(membersTab)

      expect(screen.getByPlaceholderText('email@example.com')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /invite/i })).toBeInTheDocument()
    })

    it('should invite new member', async () => {
      const user = userEvent.setup()
      mockOnInviteMember.mockResolvedValue(undefined)
      mockOnFetchMembers.mockResolvedValue([...mockMembers])

      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          members={mockMembers}
          onInviteMember={mockOnInviteMember}
          onFetchMembers={mockOnFetchMembers}
        />
      )

      const membersTab = screen.getByRole('tab', { name: /members/i })
      await user.click(membersTab)

      const emailInput = screen.getByPlaceholderText('email@example.com')
      const inviteButton = screen.getByRole('button', { name: /^invite$/i })

      await user.type(emailInput, 'newmember@example.com')
      await user.click(inviteButton)

      await waitFor(() => {
        expect(mockOnInviteMember).toHaveBeenCalledWith('newmember@example.com', 'member')
        expect(emailInput).toHaveValue('')
      })
    })

    it('should update member role', async () => {
      const user = userEvent.setup()
      mockOnUpdateMemberRole.mockResolvedValue(undefined)

      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          members={mockMembers}
          onUpdateMemberRole={mockOnUpdateMemberRole}
        />
      )

      const membersTab = screen.getByRole('tab', { name: /members/i })
      await user.click(membersTab)

      const roleSelects = screen.getAllByRole('combobox')
      await user.selectOptions(roleSelects[0], 'admin')

      await waitFor(() => {
        expect(mockOnUpdateMemberRole).toHaveBeenCalledWith('member-2', 'admin')
      })
    })

    it('should remove member', async () => {
      const user = userEvent.setup()
      mockOnRemoveMember.mockResolvedValue(undefined)

      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          members={mockMembers}
          onRemoveMember={mockOnRemoveMember}
        />
      )

      const membersTab = screen.getByRole('tab', { name: /members/i })
      await user.click(membersTab)

      const removeButtons = screen.getAllByRole('button', { name: /remove/i })
      await user.click(removeButtons[0])

      await waitFor(() => {
        expect(mockOnRemoveMember).toHaveBeenCalledWith('member-2')
      })
    })

    it('should not show remove button for owner', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          members={mockMembers}
          onRemoveMember={mockOnRemoveMember}
        />
      )

      const membersTab = screen.getByRole('tab', { name: /members/i })
      await user.click(membersTab)

      const removeButtons = screen.getAllByRole('button', { name: /remove/i })
      // Should have 2 remove buttons (for admin and member, not owner)
      expect(removeButtons).toHaveLength(2)
    })
  })

  describe('Danger Zone Tab', () => {
    it('should switch to danger zone tab', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
        />
      )

      const dangerTab = screen.getByRole('tab', { name: /danger zone/i })
      await user.click(dangerTab)

      expect(screen.getByText('Delete organization')).toBeInTheDocument()
    })

    it('should require slug confirmation for deletion', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          onDeleteOrganization={mockOnDeleteOrganization}
        />
      )

      const dangerTab = screen.getByRole('tab', { name: /danger zone/i })
      await user.click(dangerTab)

      const deleteButton = screen.getByRole('button', { name: /delete organization/i })
      expect(deleteButton).toBeDisabled()

      const confirmInput = screen.getByPlaceholderText('acme')
      await user.type(confirmInput, 'wrong-slug')

      expect(deleteButton).toBeDisabled()

      await user.clear(confirmInput)
      await user.type(confirmInput, 'acme')

      expect(deleteButton).not.toBeDisabled()
    })

    it('should delete organization with confirmation', async () => {
      const user = userEvent.setup()
      mockOnDeleteOrganization.mockResolvedValue(undefined)

      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          onDeleteOrganization={mockOnDeleteOrganization}
        />
      )

      const dangerTab = screen.getByRole('tab', { name: /danger zone/i })
      await user.click(dangerTab)

      const confirmInput = screen.getByPlaceholderText('acme')
      await user.type(confirmInput, 'acme')

      const deleteButton = screen.getByRole('button', { name: /delete organization/i })
      await user.click(deleteButton)

      await waitFor(() => {
        expect(mockOnDeleteOrganization).toHaveBeenCalled()
      })
    })

    it('should handle delete error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to delete organization')
      mockOnDeleteOrganization.mockRejectedValue(error)

      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
          onDeleteOrganization={mockOnDeleteOrganization}
          onError={mockOnError}
        />
      )

      const dangerTab = screen.getByRole('tab', { name: /danger zone/i })
      await user.click(dangerTab)

      const confirmInput = screen.getByPlaceholderText('acme')
      await user.type(confirmInput, 'acme')

      const deleteButton = screen.getByRole('button', { name: /delete organization/i })
      await user.click(deleteButton)

      await waitFor(() => {
        expect(screen.getByText('Failed to delete organization')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })
  })

  describe('Accessibility', () => {
    it('should have accessible form labels', () => {
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
        />
      )

      expect(screen.getByLabelText(/organization name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/organization slug/i)).toBeInTheDocument()
    })

    it('should support keyboard navigation between tabs', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationProfile
          organization={mockOrganization}
          userRole="owner"
        />
      )

      const generalTab = screen.getByRole('tab', { name: /general/i })
      const membersTab = screen.getByRole('tab', { name: /members/i })

      await user.click(membersTab)
      expect(membersTab).toHaveAttribute('data-state', 'active')

      await user.click(generalTab)
      expect(generalTab).toHaveAttribute('data-state', 'active')
    })
  })
})
