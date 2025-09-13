/**
 * Tests for Organizations module
 */

import { Organizations } from '../organizations';
import { HttpClient } from '../http-client';
import { NotFoundError, ValidationError, PermissionError, ConflictError } from '../errors';
import type { 
  Organization, 
  OrganizationCreateParams, 
  OrganizationUpdateParams,
  OrganizationMember,
  OrganizationInvite,
  OrganizationListParams 
} from '../types';

describe('Organizations', () => {
  let organizations: Organizations;
  let mockHttpClient: jest.Mocked<HttpClient>;

  const mockOrganization: Organization = {
    id: 'org-123',
    name: 'Test Organization',
    slug: 'test-org',
    description: 'A test organization',
    owner_id: 'user-123',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
    settings: {
      allow_invites: true,
      require_2fa: false
    }
  };

  const mockMember: OrganizationMember = {
    id: 'member-123',
    user_id: 'user-456',
    organization_id: 'org-123',
    role: 'member',
    joined_at: '2023-01-01T00:00:00Z',
    user: {
      id: 'user-456',
      email: 'member@example.com',
      first_name: 'John',
      last_name: 'Doe'
    }
  };

  beforeEach(() => {
    jest.clearAllMocks();

    mockHttpClient = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      patch: jest.fn()
    } as any;

    organizations = new Organizations(mockHttpClient);
  });

  describe('create', () => {
    it('should create organization successfully', async () => {
      const createParams: OrganizationCreateParams = {
        name: 'New Organization',
        slug: 'new-org',
        description: 'A new organization'
      };

      mockHttpClient.post.mockResolvedValue({ data: mockOrganization });

      const result = await organizations.create(createParams);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/organizations', createParams);
      expect(result).toEqual(mockOrganization);
    });

    it('should handle slug conflict', async () => {
      const createParams: OrganizationCreateParams = {
        name: 'New Organization',
        slug: 'existing-org'
      };

      mockHttpClient.post.mockRejectedValue(
        new ConflictError('Organization slug already exists')
      );

      await expect(organizations.create(createParams)).rejects.toThrow(ConflictError);
    });

    it('should handle validation errors', async () => {
      const createParams: OrganizationCreateParams = {
        name: '',
        slug: 'invalid slug'
      };

      mockHttpClient.post.mockRejectedValue(
        new ValidationError('Validation failed', [
          { field: 'name', message: 'Name is required' },
          { field: 'slug', message: 'Slug must be URL-safe' }
        ])
      );

      await expect(organizations.create(createParams)).rejects.toThrow(ValidationError);
    });
  });

  describe('getById', () => {
    it('should get organization by ID', async () => {
      mockHttpClient.get.mockResolvedValue({ data: mockOrganization });

      const result = await organizations.getById('org-123');

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/organizations/org-123');
      expect(result).toEqual(mockOrganization);
    });

    it('should handle organization not found', async () => {
      mockHttpClient.get.mockRejectedValue(
        new NotFoundError('Organization not found')
      );

      await expect(organizations.getById('non-existent')).rejects.toThrow(NotFoundError);
    });
  });

  describe('getBySlug', () => {
    it('should get organization by slug', async () => {
      mockHttpClient.get.mockResolvedValue({ data: mockOrganization });

      const result = await organizations.getBySlug('test-org');

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/organizations/by-slug/test-org');
      expect(result).toEqual(mockOrganization);
    });
  });

  describe('list', () => {
    it('should list organizations with default parameters', async () => {
      const mockResponse = {
        organizations: [mockOrganization],
        total: 1,
        page: 1,
        limit: 20
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await organizations.list();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/organizations', {
        params: {}
      });
      expect(result).toEqual(mockResponse);
    });

    it('should list organizations with custom parameters', async () => {
      const params: OrganizationListParams = {
        page: 2,
        limit: 50,
        search: 'test',
        sort_by: 'created_at',
        sort_order: 'desc'
      };

      const mockResponse = {
        organizations: [mockOrganization],
        total: 1,
        page: 2,
        limit: 50
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await organizations.list(params);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/organizations', {
        params
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('update', () => {
    it('should update organization successfully', async () => {
      const updateParams: OrganizationUpdateParams = {
        name: 'Updated Organization',
        description: 'Updated description'
      };

      const updatedOrg = { ...mockOrganization, ...updateParams };
      mockHttpClient.put.mockResolvedValue({ data: updatedOrg });

      const result = await organizations.update('org-123', updateParams);

      expect(mockHttpClient.put).toHaveBeenCalledWith('/api/v1/organizations/org-123', updateParams);
      expect(result).toEqual(updatedOrg);
    });

    it('should handle permission errors', async () => {
      mockHttpClient.put.mockRejectedValue(
        new PermissionError('You do not have permission to update this organization')
      );

      await expect(organizations.update('org-123', { name: 'New Name' })).rejects.toThrow(PermissionError);
    });
  });

  describe('delete', () => {
    it('should delete organization successfully', async () => {
      mockHttpClient.delete.mockResolvedValue({ 
        data: { 
          success: true,
          message: 'Organization deleted successfully' 
        } 
      });

      const result = await organizations.delete('org-123');

      expect(mockHttpClient.delete).toHaveBeenCalledWith('/api/v1/organizations/org-123');
      expect(result).toEqual({ 
        success: true,
        message: 'Organization deleted successfully' 
      });
    });

    it('should handle permission errors during deletion', async () => {
      mockHttpClient.delete.mockRejectedValue(
        new PermissionError('Only organization owners can delete organizations')
      );

      await expect(organizations.delete('org-123')).rejects.toThrow(PermissionError);
    });
  });

  describe('Member Management', () => {
    describe('getMembers', () => {
      it('should get organization members', async () => {
        const mockResponse = {
          members: [mockMember],
          total: 1
        };

        mockHttpClient.get.mockResolvedValue({ data: mockResponse });

        const result = await organizations.getMembers('org-123');

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/organizations/org-123/members');
        expect(result).toEqual(mockResponse);
      });

      it('should get members with pagination', async () => {
        const mockResponse = {
          members: [mockMember],
          total: 1,
          page: 2,
          limit: 10
        };

        mockHttpClient.get.mockResolvedValue({ data: mockResponse });

        const result = await organizations.getMembers('org-123', { page: 2, limit: 10 });

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/organizations/org-123/members', {
          params: { page: 2, limit: 10 }
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('addMember', () => {
      it('should add member successfully', async () => {
        const addParams = {
          user_id: 'user-789',
          role: 'member' as const
        };

        mockHttpClient.post.mockResolvedValue({ data: mockMember });

        const result = await organizations.addMember('org-123', addParams);

        expect(mockHttpClient.post).toHaveBeenCalledWith(
          '/api/v1/organizations/org-123/members',
          addParams
        );
        expect(result).toEqual(mockMember);
      });

      it('should handle user already member error', async () => {
        mockHttpClient.post.mockRejectedValue(
          new ConflictError('User is already a member of this organization')
        );

        await expect(
          organizations.addMember('org-123', { user_id: 'user-456', role: 'member' })
        ).rejects.toThrow(ConflictError);
      });
    });

    describe('updateMember', () => {
      it('should update member role successfully', async () => {
        const updatedMember = { ...mockMember, role: 'admin' as const };
        mockHttpClient.put.mockResolvedValue({ data: updatedMember });

        const result = await organizations.updateMember('org-123', 'user-456', { role: 'admin' });

        expect(mockHttpClient.put).toHaveBeenCalledWith(
          '/api/v1/organizations/org-123/members/user-456',
          { role: 'admin' }
        );
        expect(result).toEqual(updatedMember);
      });

      it('should handle permission errors when updating member', async () => {
        mockHttpClient.put.mockRejectedValue(
          new PermissionError('Only admins can update member roles')
        );

        await expect(
          organizations.updateMember('org-123', 'user-456', { role: 'admin' })
        ).rejects.toThrow(PermissionError);
      });
    });

    describe('removeMember', () => {
      it('should remove member successfully', async () => {
        mockHttpClient.delete.mockResolvedValue({ 
          data: { 
            success: true,
            message: 'Member removed successfully' 
          } 
        });

        const result = await organizations.removeMember('org-123', 'user-456');

        expect(mockHttpClient.delete).toHaveBeenCalledWith(
          '/api/v1/organizations/org-123/members/user-456'
        );
        expect(result).toEqual({ 
          success: true,
          message: 'Member removed successfully' 
        });
      });

      it('should handle removing owner error', async () => {
        mockHttpClient.delete.mockRejectedValue(
          new ValidationError('Cannot remove organization owner')
        );

        await expect(organizations.removeMember('org-123', 'user-123')).rejects.toThrow(ValidationError);
      });
    });
  });

  describe('Invitation Management', () => {
    const mockInvite: OrganizationInvite = {
      id: 'invite-123',
      organization_id: 'org-123',
      email: 'newuser@example.com',
      role: 'member',
      invited_by: 'user-123',
      status: 'pending',
      created_at: '2023-01-01T00:00:00Z',
      expires_at: '2023-01-08T00:00:00Z'
    };

    describe('getInvites', () => {
      it('should get organization invites', async () => {
        const mockResponse = {
          invites: [mockInvite],
          total: 1
        };

        mockHttpClient.get.mockResolvedValue({ data: mockResponse });

        const result = await organizations.getInvites('org-123');

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/organizations/org-123/invites');
        expect(result).toEqual(mockResponse);
      });

      it('should filter invites by status', async () => {
        const mockResponse = {
          invites: [mockInvite],
          total: 1
        };

        mockHttpClient.get.mockResolvedValue({ data: mockResponse });

        const result = await organizations.getInvites('org-123', { status: 'pending' });

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/organizations/org-123/invites', {
          params: { status: 'pending' }
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('createInvite', () => {
      it('should create invite successfully', async () => {
        const inviteParams = {
          email: 'newuser@example.com',
          role: 'member' as const
        };

        mockHttpClient.post.mockResolvedValue({ data: mockInvite });

        const result = await organizations.createInvite('org-123', inviteParams);

        expect(mockHttpClient.post).toHaveBeenCalledWith(
          '/api/v1/organizations/org-123/invites',
          inviteParams
        );
        expect(result).toEqual(mockInvite);
      });

      it('should handle existing invite error', async () => {
        mockHttpClient.post.mockRejectedValue(
          new ConflictError('An invite already exists for this email')
        );

        await expect(
          organizations.createInvite('org-123', { email: 'existing@example.com', role: 'member' })
        ).rejects.toThrow(ConflictError);
      });
    });

    describe('cancelInvite', () => {
      it('should cancel invite successfully', async () => {
        mockHttpClient.delete.mockResolvedValue({ 
          data: { 
            success: true,
            message: 'Invite cancelled successfully' 
          } 
        });

        const result = await organizations.cancelInvite('org-123', 'invite-123');

        expect(mockHttpClient.delete).toHaveBeenCalledWith(
          '/api/v1/organizations/org-123/invites/invite-123'
        );
        expect(result).toEqual({ 
          success: true,
          message: 'Invite cancelled successfully' 
        });
      });
    });

    describe('resendInvite', () => {
      it('should resend invite successfully', async () => {
        mockHttpClient.post.mockResolvedValue({ 
          data: { 
            success: true,
            invite: mockInvite
          } 
        });

        const result = await organizations.resendInvite('org-123', 'invite-123');

        expect(mockHttpClient.post).toHaveBeenCalledWith(
          '/api/v1/organizations/org-123/invites/invite-123/resend'
        );
        expect(result).toEqual({ 
          success: true,
          invite: mockInvite
        });
      });

      it('should handle expired invite error', async () => {
        mockHttpClient.post.mockRejectedValue(
          new ValidationError('Cannot resend expired invite')
        );

        await expect(organizations.resendInvite('org-123', 'invite-expired')).rejects.toThrow(ValidationError);
      });
    });

    describe('acceptInvite', () => {
      it('should accept invite successfully', async () => {
        mockHttpClient.post.mockResolvedValue({ 
          data: { 
            success: true,
            organization: mockOrganization,
            member: mockMember
          } 
        });

        const result = await organizations.acceptInvite('invite-token-123');

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/organizations/invites/accept', {
          token: 'invite-token-123'
        });
        expect(result).toEqual({ 
          success: true,
          organization: mockOrganization,
          member: mockMember
        });
      });

      it('should handle invalid invite token', async () => {
        mockHttpClient.post.mockRejectedValue(
          new ValidationError('Invalid or expired invitation token')
        );

        await expect(organizations.acceptInvite('invalid-token')).rejects.toThrow(ValidationError);
      });
    });
  });

  describe('Settings Management', () => {
    describe('getSettings', () => {
      it('should get organization settings', async () => {
        const mockSettings = {
          allow_invites: true,
          require_2fa: false,
          allowed_domains: ['example.com'],
          max_members: 100
        };

        mockHttpClient.get.mockResolvedValue({ data: mockSettings });

        const result = await organizations.getSettings('org-123');

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/organizations/org-123/settings');
        expect(result).toEqual(mockSettings);
      });
    });

    describe('updateSettings', () => {
      it('should update organization settings', async () => {
        const updatedSettings = {
          require_2fa: true,
          allowed_domains: ['example.com', 'test.com']
        };

        mockHttpClient.put.mockResolvedValue({ data: updatedSettings });

        const result = await organizations.updateSettings('org-123', updatedSettings);

        expect(mockHttpClient.put).toHaveBeenCalledWith(
          '/api/v1/organizations/org-123/settings',
          updatedSettings
        );
        expect(result).toEqual(updatedSettings);
      });

      it('should handle permission errors when updating settings', async () => {
        mockHttpClient.put.mockRejectedValue(
          new PermissionError('Only organization owners can update settings')
        );

        await expect(
          organizations.updateSettings('org-123', { require_2fa: true })
        ).rejects.toThrow(PermissionError);
      });
    });
  });
});