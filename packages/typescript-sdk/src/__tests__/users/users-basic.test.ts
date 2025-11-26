/**
 * Tests for basic Users operations
 */

import { Users } from '../../users';
import { ValidationError } from '../../errors';
import { UserStatus } from '../../types';
import type { HttpClient } from '../../http-client';

describe('Users - Basic Operations', () => {
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

  describe('CRUD operations', () => {
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

      const result = await users.search(query, filters);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/users/search', {
        params: { q: query, ...filters }
      });
      expect(result.users).toEqual(mockResponse.users);
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
});
