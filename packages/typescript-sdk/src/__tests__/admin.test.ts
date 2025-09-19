/**
 * Tests for Admin module
 */

import { Admin } from '../admin';
import { ValidationError, PermissionError } from '../errors';
import type { HttpClient } from '../http-client';

describe('Admin', () => {
  let admin: Admin;
  let mockHttpClient: jest.Mocked<HttpClient>;

  beforeEach(() => {
    mockHttpClient = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      patch: jest.fn(),
      delete: jest.fn(),
    } as any;

    admin = new Admin(mockHttpClient);
  });

  describe('getStats', () => {
    it('should get system statistics', async () => {
      const mockStats = {
        total_users: 1000,
        active_users: 850,
        total_organizations: 50,
        active_sessions: 200,
        api_requests_today: 50000,
        error_rate: 0.01,
        uptime_seconds: 86400,
        database_size: 1024000000,
        storage_used: 512000000
      };

      mockHttpClient.get.mockResolvedValue({ data: mockStats });

      const result = await admin.getStats();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/admin/stats');
      expect(result).toEqual(mockStats);
    });
  });

  describe('getSystemHealth', () => {
    it('should get system health status', async () => {
      const mockHealth = {
        status: 'healthy',
        checks: {
          database: { status: 'healthy', response_time: 5 },
          redis: { status: 'healthy', response_time: 2 },
          email: { status: 'healthy', response_time: 10 }
        },
        timestamp: '2023-01-01T00:00:00Z'
      };

      mockHttpClient.get.mockResolvedValue({ data: mockHealth });

      const result = await admin.getSystemHealth();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/admin/health');
      expect(result).toEqual(mockHealth);
    });
  });

  describe('getSystemConfig', () => {
    it('should get system configuration', async () => {
      const mockConfig = {
        environment: 'production',
        app_name: 'Plinto',
        domain: 'plinto.com',
        version: '1.0.0',
        features: {
          mfa_enabled: true,
          passkeys_enabled: true,
          oauth_enabled: true,
          webhooks_enabled: true
        }
      };

      mockHttpClient.get.mockResolvedValue({ data: mockConfig });

      const result = await admin.getSystemConfig();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/admin/config');
      expect(result).toEqual(mockConfig);
    });
  });

  describe('listAllUsers', () => {
    it('should list all users with default parameters', async () => {
      const mockUsers = [
        { id: '1', email: 'user1@example.com', status: 'active' },
        { id: '2', email: 'user2@example.com', status: 'inactive' }
      ];

      mockHttpClient.get.mockResolvedValue({ data: mockUsers });

      const result = await admin.listAllUsers();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/admin/users', {
        params: {}
      });
      expect(result.data).toEqual(mockUsers);
      expect(result.total).toEqual(mockUsers.length);
      expect(result.page).toEqual(1);
      expect(result.per_page).toEqual(20);
    });

    it('should list users with custom parameters', async () => {
      const params = {
        page: 2,
        per_page: 50,
        status: 'active' as const,
        search: 'john@'
      };

      const mockUsers = [{ id: '1', email: 'john@example.com', status: 'active' }];

      mockHttpClient.get.mockResolvedValue({ data: mockUsers });

      const result = await admin.listAllUsers(params);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/admin/users', {
        params: params
      });
      expect(result.data).toEqual(mockUsers);
      expect(result.total).toEqual(mockUsers.length);
    });
  });

  describe('updateUser', () => {
    it('should update user', async () => {
      const mockUser = {
        id: '550e8400-e29b-41d4-a716-446655440000',
        email: 'updated@example.com',
        status: 'active'
      };

      mockHttpClient.patch.mockResolvedValue({ data: mockUser });

      const updateData = { email: 'updated@example.com' };
      const result = await admin.updateUser('550e8400-e29b-41d4-a716-446655440000', updateData);

      expect(mockHttpClient.patch).toHaveBeenCalledWith('/api/v1/admin/users/550e8400-e29b-41d4-a716-446655440000', updateData);
      expect(result).toEqual(mockUser);
    });

    it('should throw error for invalid user ID', async () => {
      await expect(admin.updateUser('invalid', {})).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );
    });
  });

  describe('deleteUser', () => {
    it('should delete user', async () => {
      const mockResponse = { message: 'User deleted successfully' };

      mockHttpClient.delete.mockResolvedValue({ data: mockResponse });

      const result = await admin.deleteUser('550e8400-e29b-41d4-a716-446655440000');

      expect(mockHttpClient.delete).toHaveBeenCalledWith('/api/v1/admin/users/550e8400-e29b-41d4-a716-446655440000', {
        params: { permanent: false }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for invalid user ID', async () => {
      await expect(admin.deleteUser('invalid')).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );
    });
  });

  describe('listAllOrganizations', () => {
    it('should list all organizations', async () => {
      const mockOrganizations = [
        { id: '1', name: 'Org 1', member_count: 10 },
        { id: '2', name: 'Org 2', member_count: 5 }
      ];

      mockHttpClient.get.mockResolvedValue({ data: mockOrganizations });

      const result = await admin.listAllOrganizations();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/admin/organizations', {
        params: {}
      });
      expect(result.data).toEqual(mockOrganizations);
      expect(result.total).toEqual(mockOrganizations.length);
      expect(result.page).toEqual(1);
      expect(result.per_page).toEqual(20);
    });

    it('should list organizations with search parameters', async () => {
      const params = { search: 'tech', page: 2, per_page: 10 };

      mockHttpClient.get.mockResolvedValue({ data: { organizations: [], total: 0, page: 2, per_page: 10, pages: 0 } });

      await admin.listAllOrganizations(params);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/admin/organizations', {
        params: params
      });
    });
  });

  describe('deleteOrganization', () => {
    it('should delete organization', async () => {
      const mockResponse = { message: 'Organization deleted successfully' };

      mockHttpClient.delete.mockResolvedValue({ data: mockResponse });

      const result = await admin.deleteOrganization('550e8400-e29b-41d4-a716-446655440000');

      expect(mockHttpClient.delete).toHaveBeenCalledWith('/api/v1/admin/organizations/550e8400-e29b-41d4-a716-446655440000');
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for invalid organization ID', async () => {
      await expect(admin.deleteOrganization('invalid')).rejects.toThrow(
        new ValidationError('Invalid organization ID format')
      );
    });
  });

  describe('getActivityLogs', () => {
    it('should get activity logs entries', async () => {
      const mockActivityLogs = {
        data: [
          {
            id: '1',
            user_id: '550e8400-e29b-41d4-a716-446655440000',
            user_email: 'user@example.com',
            action: 'user.created',
            details: { email: 'user@example.com' },
            ip_address: '192.168.1.1',
            user_agent: 'Mozilla/5.0',
            created_at: '2023-01-01T00:00:00Z'
          }
        ],
        total: 100,
        page: 1,
        per_page: 50,
        total_pages: 2
      };

      mockHttpClient.get.mockResolvedValue({ data: mockActivityLogs.data });

      const result = await admin.getActivityLogs();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/admin/activity-logs', {
        params: {}
      });
      expect(result.data).toEqual(mockActivityLogs.data);
    });

    it('should get activity logs with filters', async () => {
      const filters = {
        user_id: '550e8400-e29b-41d4-a716-446655440000',
        action: 'user.created',
        start_date: '2023-01-01T00:00:00Z',
        end_date: '2023-01-31T00:00:00Z',
        page: 2
      };

      mockHttpClient.get.mockResolvedValue({ data: [] });

      await admin.getActivityLogs(filters);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/admin/activity-logs', {
        params: filters
      });
    });

    it('should throw error for invalid user_id in filters', async () => {
      const filters = { user_id: 'invalid' };

      await expect(admin.getActivityLogs(filters)).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );
    });

    it('should throw error for invalid date format', async () => {
      const filters = { start_date: 'invalid-date' };

      await expect(admin.getActivityLogs(filters)).rejects.toThrow(
        new ValidationError('Invalid start date format')
      );
    });
  });

  describe('revokeAllSessions', () => {
    it('should revoke all sessions', async () => {
      const mockResponse = { message: 'All sessions revoked successfully' };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await admin.revokeAllSessions();

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/admin/sessions/revoke-all', {
        user_id: undefined
      });
      expect(result).toEqual(mockResponse);
    });

    it('should revoke all sessions for specific user', async () => {
      const mockResponse = { message: 'User sessions revoked successfully' };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await admin.revokeAllSessions('550e8400-e29b-41d4-a716-446655440000');

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/admin/sessions/revoke-all', {
        user_id: '550e8400-e29b-41d4-a716-446655440000'
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for invalid user ID', async () => {
      await expect(admin.revokeAllSessions('invalid')).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );
    });
  });

  describe('toggleMaintenanceMode', () => {
    it('should enable maintenance mode', async () => {
      const mockResponse = {
        maintenance_mode: true,
        message: 'Maintenance mode enabled',
        note: 'System under maintenance'
      };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await admin.toggleMaintenanceMode(true, 'System under maintenance');

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/admin/maintenance-mode', {
        enabled: true,
        message: 'System under maintenance'
      });
      expect(result).toEqual(mockResponse);
    });

    it('should disable maintenance mode', async () => {
      const mockResponse = {
        maintenance_mode: false,
        message: 'Maintenance mode disabled',
        note: ''
      };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await admin.toggleMaintenanceMode(false);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/admin/maintenance-mode', {
        enabled: false,
        message: undefined
      });
      expect(result).toEqual(mockResponse);
    });
  });
});