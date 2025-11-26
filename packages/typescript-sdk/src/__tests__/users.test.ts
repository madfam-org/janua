/**
 * Tests for Users module
 */

import { Users } from '../users';
import { ValidationError } from '../errors';
import { UserStatus } from '../types';
import type { SessionListParams } from '../types';
import type { HttpClient } from '../http-client';

describe('Users', () => {
  let users: Users;
  let mockHttpClient: jest.Mocked<HttpClient>;

  beforeEach(() => {
    mockHttpClient = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      patch: jest.fn(),
      delete: jest.fn(),
    } as any;

    users = new Users(mockHttpClient);
  });

  describe('getCurrentUser', () => {
    it('should get current user profile', async () => {
      const mockUser = {
        id: '550e8400-e29b-41d4-a716-446655440000',
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User',
        email_verified: true
      };

      mockHttpClient.get.mockResolvedValue({ data: mockUser });

      const result = await users.getCurrentUser();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users/me');
      expect(result).toEqual(mockUser);
    });
  });

  describe('updateCurrentUser', () => {
    it('should update current user profile', async () => {
      const request = {
        first_name: 'Updated',
        last_name: 'Name',
        phone_number: '+1234567890',
        timezone: 'America/New_York',
        locale: 'en-US'
      };

      const mockUser = {
        id: '550e8400-e29b-41d4-a716-446655440000',
        email: 'test@example.com',
        ...request,
        email_verified: true
      };

      mockHttpClient.patch.mockResolvedValue({ data: mockUser });

      const result = await users.updateCurrentUser(request);

      expect(mockHttpClient.patch).toHaveBeenCalledWith('/api/v1/users/me', request);
      expect(result).toEqual(mockUser);
    });

    it('should throw error for invalid phone number', async () => {
      const request = { phone_number: 'invalid-phone' };

      await expect(users.updateCurrentUser(request)).rejects.toThrow(
        new ValidationError('Invalid phone number format')
      );
    });

    it('should throw error for invalid timezone', async () => {
      const request = { timezone: 'invalid-timezone!' };

      await expect(users.updateCurrentUser(request)).rejects.toThrow(
        new ValidationError('Invalid timezone format')
      );
    });

    it('should throw error for invalid locale', async () => {
      const request = { locale: 'invalid' };

      await expect(users.updateCurrentUser(request)).rejects.toThrow(
        new ValidationError('Invalid locale format (expected format: en, en-US)')
      );
    });
  });

  describe('uploadAvatar', () => {
    it('should upload user avatar successfully', async () => {
      const mockFile = new Blob(['test'], { type: 'image/jpeg' });
      Object.defineProperty(mockFile, 'size', { value: 1024 });
      Object.defineProperty(mockFile, 'type', { value: 'image/jpeg' });

      const mockResponse = { profile_image_url: 'https://example.com/avatar.jpg' };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await users.uploadAvatar(mockFile);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/users/me/avatar', expect.any(FormData), {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for oversized file', async () => {
      const mockFile = new Blob(['test'], { type: 'image/jpeg' });
      Object.defineProperty(mockFile, 'size', { value: 6 * 1024 * 1024 }); // 6MB
      Object.defineProperty(mockFile, 'type', { value: 'image/jpeg' });

      await expect(users.uploadAvatar(mockFile)).rejects.toThrow(
        new ValidationError('File size must be less than 5MB')
      );
    });

    it('should throw error for invalid file type', async () => {
      const mockFile = new Blob(['test'], { type: 'text/plain' });
      Object.defineProperty(mockFile, 'size', { value: 1024 });
      Object.defineProperty(mockFile, 'type', { value: 'text/plain' });

      await expect(users.uploadAvatar(mockFile)).rejects.toThrow(
        new ValidationError('Invalid file type. Allowed types: JPEG, PNG, GIF, WebP')
      );
    });
  });

  describe('deleteAvatar', () => {
    it('should delete user avatar', async () => {
      const mockResponse = { message: 'Avatar deleted successfully' };

      mockHttpClient.delete.mockResolvedValue({ data: mockResponse });

      const result = await users.deleteAvatar();

      expect(mockHttpClient.delete).toHaveBeenCalledWith('/api/v1/users/me/avatar');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getUserById', () => {
    it('should get user by ID successfully', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const mockUser = {
        id: userId,
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User'
      };

      mockHttpClient.get.mockResolvedValue({ data: mockUser });

      const result = await users.getUserById(userId);

      expect(mockHttpClient.get).toHaveBeenCalledWith(`/api/v1/users/${userId}`);
      expect(result).toEqual(mockUser);
    });

    it('should throw error for invalid user ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.getUserById('invalid')).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('listUsers', () => {
    it('should list users with default parameters', async () => {
      const mockUsers = [
        { id: '1', email: 'user1@example.com', first_name: 'User', last_name: 'One' },
        { id: '2', email: 'user2@example.com', first_name: 'User', last_name: 'Two' }
      ];

      const mockResponse = {
        users: mockUsers,
        total: 2,
        page: 1,
        per_page: 20
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await users.listUsers();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users', {
        params: {}
      });
      expect(result.data).toEqual(mockUsers);
      expect(result.total).toEqual(2);
      expect(result.page).toEqual(1);
      expect(result.per_page).toEqual(20);
      expect(result.total_pages).toEqual(1);
    });

    it('should list users with custom parameters', async () => {
      const params = {
        page: 2,
        per_page: 50,
        status: UserStatus.ACTIVE,
        search: 'john'
      };

      const mockResponse = {
        users: [{ id: '1', email: 'john@example.com', first_name: 'John', last_name: 'Doe' }],
        total: 1,
        page: 2,
        per_page: 50
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await users.listUsers(params);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users', {
        params: params
      });
      expect(result.data).toEqual(mockResponse.users);
      expect(result.total).toEqual(mockResponse.total);
    });

    it('should throw error for invalid pagination parameters', async () => {
      await expect(users.listUsers({ page: -1 })).rejects.toThrow(
        new ValidationError('Page must be greater than 0')
      );

      await expect(users.listUsers({ per_page: 101 })).rejects.toThrow(
        new ValidationError('Per page must be between 1 and 100')
      );
    });
  });

  describe('deleteCurrentUser', () => {
    it('should delete current user account', async () => {
      const password = 'password123';
      const mockResponse = { message: 'User account deleted successfully' };

      mockHttpClient.delete.mockResolvedValue({ data: mockResponse });

      const result = await users.deleteCurrentUser(password);

      expect(mockHttpClient.delete).toHaveBeenCalledWith('/api/v1/users/me', {
        data: { password }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for missing password', async () => {
      await expect(users.deleteCurrentUser('')).rejects.toThrow(
        new ValidationError('Password is required')
      );
    });
  });

  describe('suspendUser', () => {
    it('should suspend user successfully', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const reason = 'Violation of terms';
      const mockResponse = { message: 'User suspended successfully' };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await users.suspendUser(userId, reason);

      expect(mockHttpClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/suspend`, {
        reason
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for invalid user ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.suspendUser('invalid')).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('reactivateUser', () => {
    it('should reactivate suspended user', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const mockResponse = { message: 'User reactivated successfully' };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await users.reactivateUser(userId);

      expect(mockHttpClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/reactivate`);
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for invalid user ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.reactivateUser('invalid')).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('listSessions', () => {
    it('should list current user sessions', async () => {
      const mockSessions = [
        {
          id: 'session-1',
          user_id: '550e8400-e29b-41d4-a716-446655440000',
          ip_address: '192.168.1.1',
          device: 'Chrome on MacOS',
          created_at: '2023-01-01T00:00:00Z'
        },
        {
          id: 'session-2',
          user_id: '550e8400-e29b-41d4-a716-446655440000',
          ip_address: '192.168.1.2',
          device: 'Safari on iPhone',
          created_at: '2023-01-02T00:00:00Z'
        }
      ];

      const mockResponse = {
        sessions: mockSessions,
        total: 2
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await users.listSessions();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/sessions/', {
        params: undefined
      });
      expect(result.data).toEqual(mockSessions);
      expect(result.total).toEqual(2);
    });

    it('should list sessions with parameters', async () => {
      const params: SessionListParams = { active_only: true };
      const mockResponse = {
        sessions: [],
        total: 0
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      await users.listSessions(params);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/sessions/', {
        params
      });
    });
  });

  describe('getSession', () => {
    it('should get session details', async () => {
      const sessionId = '550e8400-e29b-41d4-a716-446655440000';
      const mockSession = {
        id: sessionId,
        user_id: '550e8400-e29b-41d4-a716-446655440001',
        ip_address: '192.168.1.1',
        device: 'Chrome on MacOS'
      };

      mockHttpClient.get.mockResolvedValue({ data: mockSession });

      const result = await users.getSession(sessionId);

      expect(mockHttpClient.get).toHaveBeenCalledWith(`/api/v1/sessions/${sessionId}`);
      expect(result).toEqual(mockSession);
    });

    it('should throw error for invalid session ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.getSession('invalid')).rejects.toThrow(
        new ValidationError('Invalid session ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('revokeSession', () => {
    it('should revoke session with single parameter (sessionId)', async () => {
      const sessionId = '550e8400-e29b-41d4-a716-446655440000';
      const mockResponse = { message: 'Session revoked successfully' };

      mockHttpClient.delete.mockResolvedValue({ data: mockResponse });

      const result = await users.revokeSession(sessionId);

      expect(mockHttpClient.delete).toHaveBeenCalledWith(`/api/v1/sessions/${sessionId}`);
      expect(result).toEqual(mockResponse);
    });

    it('should revoke session with userId and sessionId parameters', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const sessionId = '550e8400-e29b-41d4-a716-446655440001';
      const mockResponse = { message: 'Session revoked successfully' };

      mockHttpClient.delete.mockResolvedValue({ data: mockResponse });

      const result = await users.revokeSession(userId, sessionId);

      expect(mockHttpClient.delete).toHaveBeenCalledWith(`/api/v1/users/${userId}/sessions/${sessionId}`);
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for invalid session ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.revokeSession('invalid')).rejects.toThrow(
        new ValidationError('Invalid session ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('revokeAllSessions', () => {
    it('should revoke all sessions except current', async () => {
      const mockResponse = {
        message: 'All sessions revoked successfully',
        revoked_count: 3
      };

      mockHttpClient.delete.mockResolvedValue({ data: mockResponse });

      const result = await users.revokeAllSessions();

      expect(mockHttpClient.delete).toHaveBeenCalledWith('/api/v1/sessions/');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('refreshSession', () => {
    it('should refresh session expiration', async () => {
      const sessionId = '550e8400-e29b-41d4-a716-446655440000';
      const mockResponse = { message: 'Session refreshed successfully' };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await users.refreshSession(sessionId);

      expect(mockHttpClient.post).toHaveBeenCalledWith(`/api/v1/sessions/${sessionId}/refresh`);
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for invalid session ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.refreshSession('invalid')).rejects.toThrow(
        new ValidationError('Invalid session ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('getRecentActivity', () => {
    it('should get recent session activity with default limit', async () => {
      const mockResponse = {
        activities: [
          {
            session_id: 'session-1',
            activity_type: 'login',
            timestamp: '2023-01-01T00:00:00Z',
            ip_address: '192.168.1.1',
            device: 'Chrome',
            device_type: 'desktop',
            revoked: false
          }
        ],
        total: 1
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await users.getRecentActivity();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/sessions/activity/recent', {
        params: { limit: 10 }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should get recent activity with custom limit', async () => {
      const limit = 5;
      const mockResponse = { activities: [], total: 0 };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      await users.getRecentActivity(limit);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/sessions/activity/recent', {
        params: { limit }
      });
    });

    it('should throw error for invalid limit', async () => {
      await expect(users.getRecentActivity(0)).rejects.toThrow(
        new ValidationError('Limit must be between 1 and 50')
      );

      await expect(users.getRecentActivity(51)).rejects.toThrow(
        new ValidationError('Limit must be between 1 and 50')
      );
    });
  });

  describe('getSecurityAlerts', () => {
    it('should get security alerts for sessions', async () => {
      const mockResponse = {
        alerts: [
          {
            type: 'suspicious_login',
            severity: 'medium',
            message: 'Login from new location',
            locations: ['New York, NY'],
            session_ids: ['session-1']
          }
        ],
        total: 1
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await users.getSecurityAlerts();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/sessions/security/alerts');
      expect(result).toEqual(mockResponse);
    });
  });

  // User Profile Helpers Tests

  describe('getDisplayName', () => {
    it('should return display_name if available', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        display_name: 'Display Name',
        first_name: 'First',
        last_name: 'Last',
        username: 'username'
      } as any;

      const result = users.getDisplayName(user);
      expect(result).toBe('Display Name');
    });

    it('should return first and last name combined', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        first_name: 'First',
        last_name: 'Last'
      } as any;

      const result = users.getDisplayName(user);
      expect(result).toBe('First Last');
    });

    it('should return first name only', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        first_name: 'First'
      } as any;

      const result = users.getDisplayName(user);
      expect(result).toBe('First');
    });

    it('should return username', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        username: 'testuser'
      } as any;

      const result = users.getDisplayName(user);
      expect(result).toBe('testuser');
    });

    it('should return email as fallback', () => {
      const user = {
        id: '1',
        email: 'test@example.com'
      } as any;

      const result = users.getDisplayName(user);
      expect(result).toBe('test@example.com');
    });
  });

  describe('getInitials', () => {
    it('should return initials from first and last name', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        first_name: 'First',
        last_name: 'Last'
      } as any;

      const result = users.getInitials(user);
      expect(result).toBe('FL');
    });

    it('should return first two letters of first name', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        first_name: 'FirstName'
      } as any;

      const result = users.getInitials(user);
      expect(result).toBe('FI');
    });

    it('should return first two letters of username', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        username: 'testuser'
      } as any;

      const result = users.getInitials(user);
      expect(result).toBe('TE');
    });

    it('should return first two letters of email', () => {
      const user = {
        id: '1',
        email: 'test@example.com'
      } as any;

      const result = users.getInitials(user);
      expect(result).toBe('TE');
    });
  });

  describe('isProfileComplete', () => {
    it('should return true for complete profile', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        email_verified: true,
        first_name: 'First',
        last_name: 'Last',
        timezone: 'America/New_York'
      } as any;

      const result = users.isProfileComplete(user);
      expect(result).toBe(true);
    });

    it('should return false for incomplete profile', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        email_verified: false,
        first_name: 'First'
      } as any;

      const result = users.isProfileComplete(user);
      expect(result).toBe(false);
    });
  });

  describe('getProfileCompletionPercentage', () => {
    it('should calculate profile completion percentage', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        email_verified: true,
        first_name: 'First',
        last_name: 'Last',
        display_name: 'Display',
        bio: 'Bio text',
        timezone: 'America/New_York',
        profile_image_url: 'https://example.com/avatar.jpg'
      } as any;

      const result = users.getProfileCompletionPercentage(user);
      expect(result).toBe(100);
    });

    it('should handle partial completion', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        email_verified: true,
        first_name: 'First',
        last_name: '',
        display_name: null,
        bio: undefined,
        timezone: 'America/New_York',
        profile_image_url: ''
      } as any;

      // 3 out of 7 fields completed: email_verified, first_name, timezone
      const result = users.getProfileCompletionPercentage(user);
      expect(result).toBe(43); // Math.round((3/7) * 100)
    });
  });

  describe('getMissingProfileFields', () => {
    it('should return empty array for complete profile', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        email_verified: true,
        first_name: 'First',
        last_name: 'Last',
        timezone: 'America/New_York'
      } as any;

      const result = users.getMissingProfileFields(user);
      expect(result).toEqual([]);
    });

    it('should return missing required fields', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        email_verified: false,
        first_name: '',
        last_name: 'Last'
      } as any;

      const result = users.getMissingProfileFields(user);
      expect(result).toEqual(['Email verification', 'First name', 'Timezone']);
    });
  });

  describe('formatUser', () => {
    it('should format user with all computed fields', () => {
      const user = {
        id: '1',
        email: 'test@example.com',
        email_verified: true,
        first_name: 'First',
        last_name: 'Last',
        timezone: 'America/New_York'
      } as any;

      const result = users.formatUser(user);

      expect(result.displayName).toBe('First Last');
      expect(result.initials).toBe('FL');
      expect(result.profileComplete).toBe(true);
      expect(result.completionPercentage).toBe(57); // 4 out of 7 fields
      expect(result.missingFields).toEqual([]);
    });
  });

  // Backward Compatibility Alias Methods Tests

  describe('getById (alias)', () => {
    it('should call getUserById', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const mockUser = {
        id: userId,
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User'
      };

      mockHttpClient.get.mockResolvedValue({ data: mockUser });

      const result = await users.getById(userId);

      expect(mockHttpClient.get).toHaveBeenCalledWith(`/api/v1/users/${userId}`);
      expect(result).toEqual(mockUser);
    });
  });

  describe('getByEmail', () => {
    it('should get user by email successfully', async () => {
      const email = 'test@example.com';
      const mockUser = {
        id: '550e8400-e29b-41d4-a716-446655440000',
        email,
        first_name: 'Test',
        last_name: 'User'
      };

      mockHttpClient.get.mockResolvedValue({ data: mockUser });

      const result = await users.getByEmail(email);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users/by-email', {
        params: { email }
      });
      expect(result).toEqual(mockUser);
    });

    it('should throw error for invalid email format', async () => {
      await expect(users.getByEmail('invalid-email')).rejects.toThrow(
        new ValidationError('Invalid email format')
      );
    });
  });

  describe('list (alias)', () => {
    it('should list users with default parameters', async () => {
      const mockResponse = {
        users: [{ id: '1', email: 'user1@example.com' }],
        total: 1,
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

    it('should throw error for invalid pagination parameters', async () => {
      await expect(users.list({ page: -1 })).rejects.toThrow(
        new ValidationError('Page must be greater than 0')
      );
    });
  });

  describe('search', () => {
    it('should search users by query', async () => {
      const query = 'john';
      const mockResponse = {
        users: [{ id: '1', email: 'john@example.com' }],
        total: 1,
        page: 1,
        limit: 20
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await users.search(query);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users/search', {
        params: { q: query }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should search with filters', async () => {
      const query = 'admin';
      const filters = { role: 'admin' };
      const mockResponse = {
        users: [],
        total: 0,
        page: 1,
        limit: 20
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      await users.search(query, filters);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users/search', {
        params: { q: query, ...filters }
      });
    });
  });

  describe('create', () => {
    it('should create a new user', async () => {
      const userData = {
        email: 'newuser@example.com',
        first_name: 'New',
        last_name: 'User'
      };

      const createdUser = {
        id: '550e8400-e29b-41d4-a716-446655440000',
        ...userData,
        email_verified: false
      };

      mockHttpClient.post.mockResolvedValue({ data: createdUser });

      const result = await users.create(userData);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/users', userData);
      expect(result).toEqual(createdUser);
    });
  });

  describe('update', () => {
    it('should update user successfully', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const userData = {
        first_name: 'Updated',
        last_name: 'Name'
      };

      const updatedUser = {
        id: userId,
        email: 'test@example.com',
        ...userData
      };

      mockHttpClient.put.mockResolvedValue({ data: updatedUser });

      const result = await users.update(userId, userData);

      expect(mockHttpClient.put).toHaveBeenCalledWith(`/api/v1/users/${userId}`, userData);
      expect(result).toEqual(updatedUser);
    });

    it('should throw error for invalid user ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.update('invalid', {})).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('delete', () => {
    it('should delete user successfully', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const mockResponse = { message: 'User deleted successfully' };

      mockHttpClient.delete.mockResolvedValue({ data: mockResponse });

      const result = await users.delete(userId);

      expect(mockHttpClient.delete).toHaveBeenCalledWith(`/api/v1/users/${userId}`);
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for invalid user ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.delete('invalid')).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('suspend (alias)', () => {
    it('should call suspendUser', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const reason = 'Violation of terms';
      const mockResponse = { message: 'User suspended successfully' };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await users.suspend(userId, reason);

      expect(mockHttpClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/suspend`, {
        reason
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('unsuspend', () => {
    it('should unsuspend user successfully', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const mockResponse = { message: 'User unsuspended successfully' };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await users.unsuspend(userId);

      expect(mockHttpClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/unsuspend`);
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for invalid user ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.unsuspend('invalid')).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('getSessions (alias)', () => {
    it('should get user sessions successfully', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const mockSessions = [
        {
          id: 'session-1',
          user_id: userId,
          ip_address: '192.168.1.1',
          device: 'Chrome on MacOS',
          created_at: '2023-01-01T00:00:00Z'
        }
      ];

      mockHttpClient.get.mockResolvedValue({
        data: { sessions: mockSessions }
      });

      const result = await users.getSessions(userId);

      expect(mockHttpClient.get).toHaveBeenCalledWith(`/api/v1/users/${userId}/sessions`);
      expect(result).toEqual(mockSessions);
    });

    it('should throw error for invalid user ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.getSessions('invalid')).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('getPermissions', () => {
    it('should get user permissions successfully', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const mockPermissions = [
        'users.read',
        'users.write',
        'organizations.read'
      ];

      mockHttpClient.get.mockResolvedValue({
        data: { permissions: mockPermissions }
      });

      const result = await users.getPermissions(userId);

      expect(mockHttpClient.get).toHaveBeenCalledWith(`/api/v1/users/${userId}/permissions`);
      expect(result).toEqual(mockPermissions);
    });

    it('should throw error for invalid user ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.getPermissions('invalid')).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );

      delete process.env.NODE_ENV;
    });
  });

  describe('updatePermissions', () => {
    it('should update user permissions successfully', async () => {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const permissions = [
        'users.read',
        'users.write',
        'organizations.read'
      ];

      const mockResponse = {
        success: true,
        permissions
      };

      mockHttpClient.put.mockResolvedValue({ data: mockResponse });

      const result = await users.updatePermissions(userId, permissions);

      expect(mockHttpClient.put).toHaveBeenCalledWith(
        `/api/v1/users/${userId}/permissions`,
        { permissions }
      );
      expect(result).toEqual(mockResponse);
    });

    it('should throw error for invalid user ID', async () => {
      process.env.NODE_ENV = 'production';

      await expect(users.updatePermissions('invalid', [])).rejects.toThrow(
        new ValidationError('Invalid user ID format')
      );

      delete process.env.NODE_ENV;
    });
  });
});
