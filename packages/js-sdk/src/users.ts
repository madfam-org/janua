import { HttpClient } from './utils/http';
import { User, UpdateUserRequest, PlintoError } from './types';

export class UserClient {
  private http: HttpClient;

  constructor(http: HttpClient) {
    this.http = http;
  }

  async getUser(userId?: string): Promise<User> {
    const path = userId ? `/api/v1/users/${userId}` : '/api/v1/auth/me';
    return this.http.get<User>(path);
  }

  async updateUser(userId: string, data: UpdateUserRequest): Promise<User> {
    return this.http.patch<User>(`/api/v1/users/${userId}`, data);
  }

  async updateCurrentUser(data: UpdateUserRequest): Promise<User> {
    return this.http.patch<User>('/api/v1/auth/me', data);
  }

  async deleteUser(userId: string): Promise<void> {
    await this.http.delete(`/api/v1/users/${userId}`);
  }

  async deleteCurrentUser(): Promise<void> {
    await this.http.delete('/api/v1/auth/me');
  }

  async listUsers(params?: {
    limit?: number;
    offset?: number;
    email?: string;
    search?: string;
    orderBy?: string;
  }): Promise<{ users: User[]; total: number }> {
    return this.http.get('/api/v1/users', { params: params as any });
  }

  async uploadProfileImage(file: File): Promise<{ url: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.http.post<{ url: string }>(
      '/api/v1/users/profile-image',
      formData,
      {
        headers: {
          // Remove Content-Type to let browser set it with boundary
        },
      }
    );

    return response;
  }

  async removeProfileImage(): Promise<void> {
    await this.http.delete('/api/v1/users/profile-image');
  }

  async getUserSessions(userId?: string): Promise<any[]> {
    const path = userId ? `/api/v1/users/${userId}/sessions` : '/api/v1/auth/sessions';
    return this.http.get<any[]>(path);
  }

  async revokeSession(sessionId: string): Promise<void> {
    await this.http.post(`/api/v1/auth/sessions/${sessionId}/revoke`);
  }

  async revokeAllSessions(except?: string[]): Promise<void> {
    await this.http.post('/api/v1/auth/sessions/revoke-all', { except });
  }

  async getUserMetadata(userId?: string): Promise<Record<string, any>> {
    const path = userId ? `/api/v1/users/${userId}/metadata` : '/api/v1/auth/metadata';
    return this.http.get<Record<string, any>>(path);
  }

  async updateUserMetadata(
    metadata: Record<string, any>,
    userId?: string
  ): Promise<Record<string, any>> {
    const path = userId ? `/api/v1/users/${userId}/metadata` : '/api/v1/auth/metadata';
    return this.http.patch<Record<string, any>>(path, metadata);
  }

  async getUserPublicProfile(username: string): Promise<{
    username: string;
    firstName?: string;
    lastName?: string;
    profileImageUrl?: string;
    createdAt: string;
  }> {
    return this.http.get(`/api/v1/users/profile/${username}`);
  }

  async checkUsernameAvailability(username: string): Promise<{ available: boolean }> {
    return this.http.get(`/api/v1/users/username/check`, {
      params: { username },
    });
  }

  async checkEmailAvailability(email: string): Promise<{ available: boolean }> {
    return this.http.get(`/api/v1/users/email/check`, {
      params: { email },
    });
  }

  async exportUserData(): Promise<Blob> {
    const response = await this.http.request<Response>(
      'GET',
      '/api/v1/users/export',
      {
        headers: {
          Accept: 'application/json',
        },
      }
    );

    if (!(response instanceof Blob)) {
      throw new Error('Invalid response format') as PlintoError;
    }

    return response;
  }

  async getUserActivityLog(params?: {
    limit?: number;
    offset?: number;
    startDate?: string;
    endDate?: string;
  }): Promise<{
    activities: Array<{
      id: string;
      type: string;
      timestamp: string;
      details: Record<string, any>;
    }>;
    total: number;
  }> {
    return this.http.get('/api/v1/users/activity', { params: params as any });
  }
}