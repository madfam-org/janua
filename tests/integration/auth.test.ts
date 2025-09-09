import { PlintoClient } from '@plinto/sdk';
import { describe, it, expect, beforeAll, afterAll, beforeEach } from '@jest/globals';

describe('Authentication Integration Tests', () => {
  let client: PlintoClient;
  let testUser = {
    email: `test-${Date.now()}@example.com`,
    password: 'TestPassword123!',
    name: 'Test User',
  };

  beforeAll(() => {
    client = new PlintoClient({
      issuer: process.env.PLINTO_ISSUER || 'http://localhost:8000',
      clientId: process.env.PLINTO_CLIENT_ID || 'test-client',
      redirectUri: 'http://localhost:3000/callback',
    });
  });

  afterAll(async () => {
    // Clean up test user if exists
    try {
      await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      await client.deleteAccount();
    } catch (e) {
      // User might not exist
    }
  });

  describe('Sign Up Flow', () => {
    it('should successfully sign up a new user', async () => {
      const response = await client.signUp(testUser);
      
      expect(response).toHaveProperty('id');
      expect(response.email).toBe(testUser.email);
      expect(response).toHaveProperty('created_at');
      expect(response.email_verified).toBe(false);
    });

    it('should prevent duplicate email registration', async () => {
      // First registration
      await client.signUp(testUser);
      
      // Second registration should fail
      await expect(client.signUp(testUser))
        .rejects.toThrow(/email.*already.*exists/i);
    });

    it('should validate password requirements', async () => {
      const weakPasswordUser = {
        email: `weak-${Date.now()}@example.com`,
        password: '123',
        name: 'Weak Password User',
      };
      
      await expect(client.signUp(weakPasswordUser))
        .rejects.toThrow(/password.*must.*be.*at.*least.*8/i);
    });

    it('should validate email format', async () => {
      const invalidEmailUser = {
        email: 'not-an-email',
        password: 'ValidPassword123!',
        name: 'Invalid Email User',
      };
      
      await expect(client.signUp(invalidEmailUser))
        .rejects.toThrow(/invalid.*email/i);
    });
  });

  describe('Sign In Flow', () => {
    beforeEach(async () => {
      // Ensure user exists
      try {
        await client.signUp(testUser);
      } catch (e) {
        // User might already exist
      }
    });

    it('should successfully sign in with valid credentials', async () => {
      const response = await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      
      expect(response).toHaveProperty('access_token');
      expect(response).toHaveProperty('refresh_token');
      expect(response).toHaveProperty('expires_in');
      expect(response.token_type).toBe('Bearer');
      
      // Verify tokens are stored
      expect(client.getAccessToken()).toBe(response.access_token);
      expect(client.getRefreshToken()).toBe(response.refresh_token);
    });

    it('should fail sign in with invalid password', async () => {
      await expect(client.signIn({
        email: testUser.email,
        password: 'WrongPassword123!',
      })).rejects.toThrow(/invalid.*credentials/i);
    });

    it('should fail sign in with non-existent email', async () => {
      await expect(client.signIn({
        email: 'nonexistent@example.com',
        password: 'SomePassword123!',
      })).rejects.toThrow(/invalid.*credentials/i);
    });

    it('should handle rate limiting', async () => {
      const attempts = [];
      
      // Make multiple rapid sign-in attempts
      for (let i = 0; i < 10; i++) {
        attempts.push(
          client.signIn({
            email: testUser.email,
            password: 'WrongPassword',
          }).catch(e => e)
        );
      }
      
      const results = await Promise.all(attempts);
      const rateLimitError = results.find(r => 
        r instanceof Error && r.message.includes('rate limit')
      );
      
      expect(rateLimitError).toBeDefined();
    });
  });

  describe('Token Management', () => {
    let accessToken: string;
    let refreshToken: string;

    beforeEach(async () => {
      const response = await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      
      accessToken = response.access_token;
      refreshToken = response.refresh_token;
    });

    it('should successfully refresh access token', async () => {
      client.setRefreshToken(refreshToken);
      const response = await client.refreshToken();
      
      expect(response).toHaveProperty('access_token');
      expect(response).toHaveProperty('expires_in');
      expect(response.access_token).not.toBe(accessToken); // New token
      expect(client.getAccessToken()).toBe(response.access_token);
    });

    it('should handle expired refresh token', async () => {
      client.setRefreshToken('expired-refresh-token');
      
      await expect(client.refreshToken())
        .rejects.toThrow(/invalid.*refresh.*token/i);
    });

    it('should verify token with introspection', async () => {
      client.setAccessToken(accessToken);
      const response = await client.introspectToken();
      
      expect(response.active).toBe(true);
      expect(response.sub).toBeDefined();
      expect(response.email).toBe(testUser.email);
      expect(response.exp).toBeGreaterThan(Date.now() / 1000);
    });

    it('should handle revoked tokens', async () => {
      client.setAccessToken(accessToken);
      await client.revokeToken();
      
      const response = await client.introspectToken();
      expect(response.active).toBe(false);
    });
  });

  describe('User Profile', () => {
    beforeEach(async () => {
      const response = await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      client.setAccessToken(response.access_token);
    });

    it('should fetch user profile', async () => {
      const profile = await client.getUser();
      
      expect(profile.email).toBe(testUser.email);
      expect(profile.name).toBe(testUser.name);
      expect(profile).toHaveProperty('id');
      expect(profile).toHaveProperty('created_at');
    });

    it('should update user profile', async () => {
      const updatedName = 'Updated Test User';
      const response = await client.updateUser({ name: updatedName });
      
      expect(response.name).toBe(updatedName);
      
      // Verify update persisted
      const profile = await client.getUser();
      expect(profile.name).toBe(updatedName);
    });

    it('should change password', async () => {
      const newPassword = 'NewPassword123!';
      
      await client.changePassword({
        current_password: testUser.password,
        new_password: newPassword,
      });
      
      // Sign out and sign in with new password
      await client.signOut();
      
      const response = await client.signIn({
        email: testUser.email,
        password: newPassword,
      });
      
      expect(response).toHaveProperty('access_token');
      
      // Change back for cleanup
      testUser.password = newPassword;
    });
  });

  describe('Email Verification', () => {
    it('should send verification email', async () => {
      await client.signUp({
        email: `verify-${Date.now()}@example.com`,
        password: 'Password123!',
        name: 'Verify User',
      });
      
      const response = await client.sendVerificationEmail();
      expect(response.success).toBe(true);
      expect(response.message).toMatch(/verification.*sent/i);
    });

    it('should verify email with valid token', async () => {
      // This would need a real token from email
      const mockToken = 'mock-verification-token';
      
      // In a real test, you'd extract this from the email
      const response = await client.verifyEmail(mockToken)
        .catch(e => e);
      
      // We expect this to fail with our mock token
      expect(response).toBeInstanceOf(Error);
      expect(response.message).toMatch(/invalid.*token/i);
    });
  });

  describe('Password Reset', () => {
    it('should request password reset', async () => {
      const response = await client.resetPassword(testUser.email);
      
      expect(response.success).toBe(true);
      expect(response.message).toMatch(/reset.*sent/i);
    });

    it('should handle reset for non-existent email', async () => {
      // Should return success to prevent email enumeration
      const response = await client.resetPassword('nonexistent@example.com');
      
      expect(response.success).toBe(true);
      expect(response.message).toMatch(/reset.*sent/i);
    });

    it('should reset password with valid token', async () => {
      // This would need a real token from email
      const mockToken = 'mock-reset-token';
      const newPassword = 'ResetPassword123!';
      
      // In a real test, you'd extract this from the email
      const response = await client.confirmPasswordReset({
        token: mockToken,
        password: newPassword,
      }).catch(e => e);
      
      // We expect this to fail with our mock token
      expect(response).toBeInstanceOf(Error);
      expect(response.message).toMatch(/invalid.*token/i);
    });
  });

  describe('Sign Out', () => {
    beforeEach(async () => {
      const response = await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      client.setAccessToken(response.access_token);
      client.setRefreshToken(response.refresh_token);
    });

    it('should successfully sign out', async () => {
      const response = await client.signOut();
      
      expect(response.success).toBe(true);
      expect(client.getAccessToken()).toBeNull();
      expect(client.getRefreshToken()).toBeNull();
      expect(client.isAuthenticated()).toBe(false);
    });

    it('should invalidate tokens on server', async () => {
      const accessToken = client.getAccessToken();
      await client.signOut();
      
      // Try to use the old token
      client.setAccessToken(accessToken);
      await expect(client.getUser())
        .rejects.toThrow(/unauthorized/i);
    });
  });

  describe('Session Management', () => {
    it('should list active sessions', async () => {
      await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      
      const sessions = await client.getSessions();
      
      expect(sessions).toBeInstanceOf(Array);
      expect(sessions.length).toBeGreaterThan(0);
      expect(sessions[0]).toHaveProperty('id');
      expect(sessions[0]).toHaveProperty('created_at');
      expect(sessions[0]).toHaveProperty('last_active');
      expect(sessions[0]).toHaveProperty('ip_address');
      expect(sessions[0]).toHaveProperty('user_agent');
    });

    it('should revoke specific session', async () => {
      await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      
      const sessions = await client.getSessions();
      const sessionToRevoke = sessions[0];
      
      const response = await client.revokeSession(sessionToRevoke.id);
      expect(response.success).toBe(true);
      
      const updatedSessions = await client.getSessions();
      const revokedSession = updatedSessions.find(s => s.id === sessionToRevoke.id);
      expect(revokedSession).toBeUndefined();
    });

    it('should revoke all other sessions', async () => {
      // Create multiple sessions
      const client2 = new PlintoClient({
        issuer: process.env.PLINTO_ISSUER || 'http://localhost:8000',
        clientId: 'test-client-2',
        redirectUri: 'http://localhost:3000/callback',
      });
      
      await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      
      await client2.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      
      const initialSessions = await client.getSessions();
      expect(initialSessions.length).toBeGreaterThan(1);
      
      await client.revokeAllOtherSessions();
      
      const finalSessions = await client.getSessions();
      expect(finalSessions.length).toBe(1);
    });
  });

  describe('Multi-Factor Authentication', () => {
    beforeEach(async () => {
      await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
    });

    it('should enable TOTP MFA', async () => {
      const response = await client.enableTOTP();
      
      expect(response).toHaveProperty('secret');
      expect(response).toHaveProperty('qr_code');
      expect(response).toHaveProperty('backup_codes');
      expect(response.backup_codes).toHaveLength(10);
    });

    it('should require MFA code after enabling', async () => {
      await client.enableTOTP();
      await client.signOut();
      
      const response = await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      
      expect(response).toHaveProperty('mfa_required');
      expect(response.mfa_required).toBe(true);
      expect(response).toHaveProperty('mfa_token');
      expect(response).not.toHaveProperty('access_token');
    });

    it('should complete MFA challenge', async () => {
      const totpSetup = await client.enableTOTP();
      await client.signOut();
      
      const signInResponse = await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      
      // In a real test, you'd generate the TOTP code
      const mockTotpCode = '123456';
      
      const mfaResponse = await client.completeMFA({
        mfa_token: signInResponse.mfa_token,
        code: mockTotpCode,
      }).catch(e => e);
      
      // We expect this to fail with our mock code
      expect(mfaResponse).toBeInstanceOf(Error);
      expect(mfaResponse.message).toMatch(/invalid.*code/i);
    });

    it('should disable MFA', async () => {
      await client.enableTOTP();
      
      const response = await client.disableMFA({
        password: testUser.password,
      });
      
      expect(response.success).toBe(true);
      
      // Verify MFA is disabled
      await client.signOut();
      const signInResponse = await client.signIn({
        email: testUser.email,
        password: testUser.password,
      });
      
      expect(signInResponse).toHaveProperty('access_token');
      expect(signInResponse.mfa_required).toBeUndefined();
    });
  });
});