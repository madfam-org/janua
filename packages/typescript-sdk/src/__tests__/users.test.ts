/**
 * Tests for Users module
 */

import { Users } from '../users';
import { HttpClient } from '../http-client';
import { NotFoundError, ValidationError, PermissionError } from '../errors';
import { userFixtures } from '../../../../tests/fixtures/data';
import type { User, UserListParams, UserUpdateParams } from '../types';

describe('Users', () => {
  let users: Users;
  let mockHttpClient: jest.Mocked<HttpClient>;

  beforeEach(() => {
    jest.clearAllMocks();

    mockHttpClient = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      patch: jest.fn()
    } as any;

    users = new Users(mockHttpClient);
  });

  describe('getById', () => {
    it('should get user by ID successfully', async () => {
      const userId = 'user-123';
      const mockUser = userFixtures.verifiedUser;

      mockHttpClient.get.mockResolvedValue({ data: mockUser });

      const result = await users.getById(userId);

      expect(mockHttpClient.get).toHaveBeenCalledWith(`/api/v1/users/${userId}`);
      expect(result).toEqual(mockUser);
    });

    it('should handle user not found', async () => {
      const userId = 'non-existent';

      mockHttpClient.get.mockRejectedValue(
        new NotFoundError('User not found')
      );

      await expect(users.getById(userId)).rejects.toThrow(NotFoundError);
    });
  });

  describe('getByEmail', () => {
    it('should get user by email successfully', async () => {
      const email = 'test@example.com';
      const mockUser = userFixtures.verifiedUser;

      mockHttpClient.get.mockResolvedValue({ data: mockUser });

      const result = await users.getByEmail(email);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users/by-email', {
        params: { email }
      });
      expect(result).toEqual(mockUser);
    });

    it('should handle invalid email format', async () => {
      const email = 'invalid-email';

      mockHttpClient.get.mockRejectedValue(
        new ValidationError('Invalid email format')
      );

      await expect(users.getByEmail(email)).rejects.toThrow(ValidationError);
    });
  });

  describe('list', () => {
    it('should list users with default parameters', async () => {
      const mockResponse = {
        users: [userFixtures.verifiedUser, userFixtures.unverifiedUser],
        total: 2,
        page: 1,
        limit: 20
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await users.list();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users', {
        params: {}
      });
      expect(result).toEqual(mockResponse);
    });

    it('should list users with custom parameters', async () => {
      const params: UserListParams = {
        page: 2,
        limit: 50,
        search: 'john',
        sort_by: 'created_at',
        sort_order: 'desc',
        filter: {
          verified: true,
          role: 'admin'
        }
      };

      const mockResponse = {
        users: [userFixtures.adminUser],
        total: 1,
        page: 2,
        limit: 50
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await users.list(params);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users', {
        params: params
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('search', () => {
    it('should search users by query', async () => {
      const query = 'john doe';
      const mockResponse = {
        users: [userFixtures.verifiedUser],
        total: 1
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await users.search(query);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users/search', {
        params: { q: query }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should search with additional filters', async () => {
      const query = 'admin';
      const filters = {
        role: 'admin',
        verified: true
      };

      const mockResponse = {
        users: [userFixtures.adminUser],
        total: 1
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await users.search(query, filters);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users/search', {
        params: { q: query, ...filters }
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('create', () => {
    it('should create a new user successfully', async () => {
      const newUserData = {
        email: 'newuser@example.com',
        first_name: 'New',
        last_name: 'User',
        role: 'user' as const
      };

      const createdUser = {
        id: 'user-new-123',
        ...newUserData,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };

      mockHttpClient.post.mockResolvedValue({ data: createdUser });

      const result = await users.create(newUserData);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/users', newUserData);
      expect(result).toEqual(createdUser);
    });

    it('should handle validation errors during user creation', async () => {
      const invalidUserData = {
        email: 'invalid-email',
        first_name: '',
        last_name: ''
      };

      mockHttpClient.post.mockRejectedValue(
        new ValidationError('Validation failed', [
          { field: 'email', message: 'Invalid email format' },
          { field: 'first_name', message: 'First name is required' }
        ])
      );

      await expect(users.create(invalidUserData as any)).rejects.toThrow(ValidationError);
    });
  });

  describe('update', () => {
    it('should update user successfully', async () => {
      const userId = 'user-123';
      const updates: UserUpdateParams = {
        first_name: 'Updated',
        last_name: 'Name',
        phone: '+1234567890'
      };

      const updatedUser = {
        ...userFixtures.verifiedUser,
        ...updates
      };

      mockHttpClient.put.mockResolvedValue({ data: updatedUser });

      const result = await users.update(userId, updates);

      expect(mockHttpClient.put).toHaveBeenCalledWith(`/api/v1/users/${userId}`, updates);
      expect(result).toEqual(updatedUser);
    });

    it('should handle permission errors', async () => {
      const userId = 'user-123';
      const updates = { role: 'admin' };

      mockHttpClient.put.mockRejectedValue(
        new PermissionError('Insufficient permissions to update user role')
      );

      await expect(users.update(userId, updates)).rejects.toThrow(PermissionError);
    });
  });

  describe('delete', () => {
    it('should delete user successfully', async () => {
      const userId = 'user-123';

      mockHttpClient.delete.mockResolvedValue({ 
        data: { 
          success: true,
          message: 'User deleted successfully' 
        } 
      });

      const result = await users.delete(userId);

      expect(mockHttpClient.delete).toHaveBeenCalledWith(`/api/v1/users/${userId}`);
      expect(result).toEqual({ 
        success: true,
        message: 'User deleted successfully' 
      });
    });

    it('should handle permission errors during deletion', async () => {
      const userId = 'user-123';

      mockHttpClient.delete.mockRejectedValue(
        new PermissionError('Cannot delete user')
      );

      await expect(users.delete(userId)).rejects.toThrow(PermissionError);
    });
  });

  describe('suspend', () => {
    it('should suspend user successfully', async () => {
      const userId = 'user-123';
      const reason = 'Violation of terms of service';

      mockHttpClient.post.mockResolvedValue({ 
        data: { 
          success: true,
          user: { ...userFixtures.verifiedUser, suspended: true }
        } 
      });

      const result = await users.suspend(userId, reason);

      expect(mockHttpClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/suspend`, { 
        reason 
      });
      expect(result).toEqual({ 
        success: true,
        user: { ...userFixtures.verifiedUser, suspended: true }
      });
    });
  });

  describe('unsuspend', () => {
    it('should unsuspend user successfully', async () => {
      const userId = 'user-123';

      mockHttpClient.post.mockResolvedValue({ 
        data: { 
          success: true,
          user: { ...userFixtures.verifiedUser, suspended: false }
        } 
      });

      const result = await users.unsuspend(userId);

      expect(mockHttpClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/unsuspend`);
      expect(result).toEqual({ 
        success: true,
        user: { ...userFixtures.verifiedUser, suspended: false }
      });
    });
  });

  describe('getSessions', () => {
    it('should get user sessions successfully', async () => {
      const userId = 'user-123';
      const mockSessions = [
        {
          id: 'session-1',
          user_id: userId,
          ip_address: '192.168.1.1',
          user_agent: 'Mozilla/5.0',
          created_at: new Date().toISOString(),
          last_active: new Date().toISOString()
        },
        {
          id: 'session-2',
          user_id: userId,
          ip_address: '192.168.1.2',
          user_agent: 'Chrome/96.0',
          created_at: new Date().toISOString(),
          last_active: new Date().toISOString()
        }
      ];

      mockHttpClient.get.mockResolvedValue({ 
        data: { 
          sessions: mockSessions
        } 
      });

      const result = await users.getSessions(userId);

      expect(mockHttpClient.get).toHaveBeenCalledWith(`/api/v1/users/${userId}/sessions`);
      expect(result).toEqual(mockSessions);
    });
  });

  describe('revokeSession', () => {
    it('should revoke user session successfully', async () => {
      const userId = 'user-123';
      const sessionId = 'session-1';

      mockHttpClient.delete.mockResolvedValue({ 
        data: { 
          success: true,
          message: 'Session revoked successfully'
        } 
      });

      const result = await users.revokeSession(userId, sessionId);

      expect(mockHttpClient.delete).toHaveBeenCalledWith(
        `/api/v1/users/${userId}/sessions/${sessionId}`
      );
      expect(result).toEqual({ 
        success: true,
        message: 'Session revoked successfully'
      });
    });
  });

  describe('getPermissions', () => {
    it('should get user permissions successfully', async () => {
      const userId = 'user-123';
      const mockPermissions = [
        'users.read',
        'users.write',
        'organizations.read'
      ];

      mockHttpClient.get.mockResolvedValue({ 
        data: { 
          permissions: mockPermissions
        } 
      });

      const result = await users.getPermissions(userId);

      expect(mockHttpClient.get).toHaveBeenCalledWith(`/api/v1/users/${userId}/permissions`);
      expect(result).toEqual(mockPermissions);
    });
  });

  describe('updatePermissions', () => {
    it('should update user permissions successfully', async () => {
      const userId = 'user-123';
      const permissions = [
        'users.read',
        'users.write',
        'organizations.read',
        'organizations.write'
      ];

      mockHttpClient.put.mockResolvedValue({ 
        data: { 
          success: true,
          permissions
        } 
      });

      const result = await users.updatePermissions(userId, permissions);

      expect(mockHttpClient.put).toHaveBeenCalledWith(
        `/api/v1/users/${userId}/permissions`,
        { permissions }
      );
      expect(result).toEqual({ 
        success: true,
        permissions
      });
    });

    it('should handle permission errors when updating permissions', async () => {
      const userId = 'user-123';
      const permissions = ['admin.all'];

      mockHttpClient.put.mockRejectedValue(
        new PermissionError('Cannot grant admin permissions')
      );

      await expect(users.updatePermissions(userId, permissions)).rejects.toThrow(PermissionError);
    });
  });
});