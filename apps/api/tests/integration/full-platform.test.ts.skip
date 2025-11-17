import { describe, it, expect, beforeAll, afterAll, beforeEach } from '@jest/globals';
import request from 'supertest';
import { io, Socket } from 'socket.io-client';
import { createTestApp } from '../helpers/test-app';
import { seedDatabase } from '../helpers/seed';
import { generateTestData } from '../helpers/generators';

describe('Plinto Platform - Full Integration Tests', () => {
  let app: any;
  let adminToken: string;
  let userToken: string;
  let organizationId: string;
  let userId: string;
  let socket: Socket;

  beforeAll(async () => {
    app = await createTestApp();
    await seedDatabase();
    
    // Create test organization and users
    const orgRes = await request(app)
      .post('/api/organizations')
      .send({
        name: 'Test Organization',
        slug: 'test-org',
        plan: 'pro',
      });
    
    organizationId = orgRes.body.id;
    
    // Create admin user
    const adminRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'admin@test.com',
        password: 'SecurePass123!',
        organizationId,
      });
    
    adminToken = adminRes.body.token;
    
    // Create regular user
    const userRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'user@test.com',
        password: 'UserPass123!',
        organizationId,
      });
    
    userToken = userRes.body.token;
    userId = userRes.body.user.id;
  });

  afterAll(async () => {
    if (socket) socket.disconnect();
    await app.close();
  });

  describe('Phase 1: Core Authentication & Security', () => {
    describe('Authentication Flow', () => {
      it('should complete full authentication flow', async () => {
        // Login
        const loginRes = await request(app)
          .post('/api/auth/login')
          .send({
            email: 'user@test.com',
            password: 'UserPass123!',
          });
        
        expect(loginRes.status).toBe(200);
        expect(loginRes.body).toHaveProperty('token');
        expect(loginRes.body).toHaveProperty('refreshToken');
        
        // Refresh token
        const refreshRes = await request(app)
          .post('/api/auth/refresh')
          .send({
            refreshToken: loginRes.body.refreshToken,
          });
        
        expect(refreshRes.status).toBe(200);
        expect(refreshRes.body).toHaveProperty('token');
        
        // Verify token
        const verifyRes = await request(app)
          .get('/api/auth/me')
          .set('Authorization', `Bearer ${refreshRes.body.token}`);
        
        expect(verifyRes.status).toBe(200);
        expect(verifyRes.body.email).toBe('user@test.com');
        
        // Logout
        const logoutRes = await request(app)
          .post('/api/auth/logout')
          .set('Authorization', `Bearer ${refreshRes.body.token}`);
        
        expect(logoutRes.status).toBe(200);
      });
    });

    describe('Session Management', () => {
      it('should manage sessions correctly', async () => {
        // Create session
        const loginRes = await request(app)
          .post('/api/auth/login')
          .send({
            email: 'user@test.com',
            password: 'UserPass123!',
          });
        
        const sessionToken = loginRes.body.token;
        
        // List sessions
        const sessionsRes = await request(app)
          .get('/api/sessions')
          .set('Authorization', `Bearer ${sessionToken}`);
        
        expect(sessionsRes.status).toBe(200);
        expect(sessionsRes.body.length).toBeGreaterThan(0);
        
        const sessionId = sessionsRes.body[0].id;
        
        // Revoke specific session
        const revokeRes = await request(app)
          .delete(`/api/sessions/${sessionId}`)
          .set('Authorization', `Bearer ${sessionToken}`);
        
        expect(revokeRes.status).toBe(200);
      });
    });

    describe('Audit Logging', () => {
      it('should track all security events', async () => {
        // Perform actions that trigger audit logs
        await request(app)
          .post('/api/auth/login')
          .send({
            email: 'user@test.com',
            password: 'UserPass123!',
          });
        
        // Query audit logs
        const logsRes = await request(app)
          .get('/api/audit-logs')
          .set('Authorization', `Bearer ${adminToken}`)
          .query({
            event: 'user.login',
            userId,
          });
        
        expect(logsRes.status).toBe(200);
        expect(logsRes.body.logs.length).toBeGreaterThan(0);
        expect(logsRes.body.logs[0].event).toBe('user.login');
      });
    });
  });

  describe('Phase 2: Advanced Authentication Features', () => {
    describe('Passkeys/WebAuthn', () => {
      it('should register and authenticate with passkey', async () => {
        // Begin registration
        const beginRes = await request(app)
          .post('/api/passkeys/register/begin')
          .set('Authorization', `Bearer ${userToken}`)
          .send({ displayName: 'Test User' });
        
        expect(beginRes.status).toBe(200);
        expect(beginRes.body).toHaveProperty('challenge');
        expect(beginRes.body).toHaveProperty('user');
        
        // Complete registration (simulated)
        const completeRes = await request(app)
          .post('/api/passkeys/register/complete')
          .set('Authorization', `Bearer ${userToken}`)
          .send({
            credentialId: 'test-credential-id',
            publicKey: 'test-public-key',
            challenge: beginRes.body.challenge,
          });
        
        expect(completeRes.status).toBe(200);
        expect(completeRes.body.success).toBe(true);
      });
    });

    describe('Multi-Factor Authentication', () => {
      it('should setup and verify TOTP MFA', async () => {
        // Setup TOTP
        const setupRes = await request(app)
          .post('/api/mfa/totp/setup')
          .set('Authorization', `Bearer ${userToken}`);
        
        expect(setupRes.status).toBe(200);
        expect(setupRes.body).toHaveProperty('secret');
        expect(setupRes.body).toHaveProperty('qrCode');
        
        // Verify TOTP (with test code)
        const verifyRes = await request(app)
          .post('/api/mfa/totp/verify')
          .set('Authorization', `Bearer ${userToken}`)
          .send({
            code: '123456', // Test environment accepts this
          });
        
        expect(verifyRes.status).toBe(200);
        expect(verifyRes.body.enabled).toBe(true);
      });
    });

    describe('Invitations System', () => {
      it('should create and accept invitations', async () => {
        // Create invitation
        const createRes = await request(app)
          .post('/api/invitations')
          .set('Authorization', `Bearer ${adminToken}`)
          .send({
            email: 'newuser@test.com',
            role: 'member',
            teams: ['engineering'],
          });
        
        expect(createRes.status).toBe(200);
        expect(createRes.body).toHaveProperty('token');
        
        // Accept invitation
        const acceptRes = await request(app)
          .post('/api/invitations/accept')
          .send({
            token: createRes.body.token,
            password: 'NewUserPass123!',
          });
        
        expect(acceptRes.status).toBe(200);
        expect(acceptRes.body).toHaveProperty('user');
        expect(acceptRes.body).toHaveProperty('token');
      });
    });

    describe('Organization Management', () => {
      it('should manage organization members and teams', async () => {
        // Add member to team
        const addTeamRes = await request(app)
          .post(`/api/organizations/${organizationId}/members/${userId}/teams`)
          .set('Authorization', `Bearer ${adminToken}`)
          .send({
            teamId: 'engineering',
          });
        
        expect(addTeamRes.status).toBe(200);
        
        // Update member role
        const updateRoleRes = await request(app)
          .put(`/api/organizations/${organizationId}/members/${userId}/role`)
          .set('Authorization', `Bearer ${adminToken}`)
          .send({
            role: 'admin',
          });
        
        expect(updateRoleRes.status).toBe(200);
        
        // Get member details
        const memberRes = await request(app)
          .get(`/api/organizations/${organizationId}/members/${userId}`)
          .set('Authorization', `Bearer ${adminToken}`);
        
        expect(memberRes.status).toBe(200);
        expect(memberRes.body.role).toBe('admin');
        expect(memberRes.body.teams).toContain('engineering');
      });
    });
  });

  describe('Phase 3: Infrastructure & Scalability', () => {
    describe('Webhook Delivery', () => {
      it('should deliver webhooks with retry logic', async () => {
        // Register webhook
        const registerRes = await request(app)
          .post('/api/webhooks')
          .set('Authorization', `Bearer ${adminToken}`)
          .send({
            url: 'https://webhook.site/test',
            events: ['user.created', 'user.updated'],
            secret: 'webhook-secret',
          });
        
        expect(registerRes.status).toBe(200);
        const webhookId = registerRes.body.id;
        
        // Trigger event that sends webhook
        await request(app)
          .post('/api/users')
          .set('Authorization', `Bearer ${adminToken}`)
          .send({
            email: 'webhook-test@test.com',
            name: 'Webhook Test User',
          });
        
        // Check webhook delivery status
        const statusRes = await request(app)
          .get(`/api/webhooks/${webhookId}/deliveries`)
          .set('Authorization', `Bearer ${adminToken}`);
        
        expect(statusRes.status).toBe(200);
        expect(statusRes.body.deliveries.length).toBeGreaterThan(0);
      });
    });

    describe('Billing & Quotas', () => {
      it('should track usage and enforce quotas', async () => {
        // Get current usage
        const usageRes = await request(app)
          .get(`/api/organizations/${organizationId}/usage`)
          .set('Authorization', `Bearer ${adminToken}`);
        
        expect(usageRes.status).toBe(200);
        expect(usageRes.body).toHaveProperty('mauUsed');
        expect(usageRes.body).toHaveProperty('storageUsed');
        
        // Update subscription
        const subRes = await request(app)
          .put(`/api/organizations/${organizationId}/subscription`)
          .set('Authorization', `Bearer ${adminToken}`)
          .send({
            plan: 'enterprise',
          });
        
        expect(subRes.status).toBe(200);
        expect(subRes.body.plan).toBe('enterprise');
        
        // Generate invoice
        const invoiceRes = await request(app)
          .post(`/api/organizations/${organizationId}/invoices/generate`)
          .set('Authorization', `Bearer ${adminToken}`);
        
        expect(invoiceRes.status).toBe(200);
        expect(invoiceRes.body).toHaveProperty('amount');
      });
    });

    describe('Rate Limiting', () => {
      it('should enforce rate limits', async () => {
        const requests = [];
        
        // Make rapid requests
        for (let i = 0; i < 15; i++) {
          requests.push(
            request(app)
              .get('/api/users')
              .set('Authorization', `Bearer ${userToken}`)
          );
        }
        
        const responses = await Promise.all(requests);
        
        // Some should be rate limited
        const rateLimited = responses.filter(r => r.status === 429);
        expect(rateLimited.length).toBeGreaterThan(0);
        
        // Check rate limit headers
        const lastResponse = responses[responses.length - 1];
        expect(lastResponse.headers).toHaveProperty('x-ratelimit-limit');
        expect(lastResponse.headers).toHaveProperty('x-ratelimit-remaining');
      });
    });
  });

  describe('Phase 4: Real-time & Analytics', () => {
    describe('GraphQL API', () => {
      it('should execute GraphQL queries and mutations', async () => {
        // Query users
        const queryRes = await request(app)
          .post('/api/graphql')
          .set('Authorization', `Bearer ${adminToken}`)
          .send({
            query: `
              query {
                users(limit: 10) {
                  id
                  email
                  profile {
                    displayName
                  }
                }
              }
            `,
          });
        
        expect(queryRes.status).toBe(200);
        expect(queryRes.body.data.users).toBeDefined();
        
        // Mutation to update user
        const mutationRes = await request(app)
          .post('/api/graphql')
          .set('Authorization', `Bearer ${userToken}`)
          .send({
            query: `
              mutation UpdateProfile($input: UpdateProfileInput!) {
                updateProfile(input: $input) {
                  id
                  displayName
                }
              }
            `,
            variables: {
              input: {
                displayName: 'Updated Name',
              },
            },
          });
        
        expect(mutationRes.status).toBe(200);
        expect(mutationRes.body.data.updateProfile.displayName).toBe('Updated Name');
      });

      it('should handle GraphQL subscriptions', async () => {
        // This would typically use WebSocket connection
        // Simulating subscription setup
        const subRes = await request(app)
          .post('/api/graphql')
          .set('Authorization', `Bearer ${userToken}`)
          .send({
            query: `
              subscription {
                userUpdated(userId: "${userId}") {
                  id
                  email
                  updatedAt
                }
              }
            `,
          });
        
        expect(subRes.status).toBe(200);
      });
    });

    describe('WebSocket Real-time', () => {
      beforeEach((done) => {
        socket = io('http://localhost:3000', {
          auth: {
            token: userToken,
          },
        });
        
        socket.on('connect', done);
      });

      it('should handle real-time messaging', (done) => {
        const testMessage = {
          room: 'test-room',
          content: 'Hello, WebSocket!',
        };
        
        // Join room
        socket.emit('join', { room: 'test-room' });
        
        // Listen for message
        socket.on('message', (data: any) => {
          expect(data.content).toBe(testMessage.content);
          done();
        });
        
        // Send message
        socket.emit('message', testMessage);
      });

      it('should track presence', (done) => {
        socket.emit('join', { room: 'presence-room' });
        
        socket.on('presence:update', (data: any) => {
          expect(data.users).toBeDefined();
          expect(data.users.length).toBeGreaterThan(0);
          done();
        });
        
        socket.emit('presence:ping');
      });
    });

    describe('Analytics & Reporting', () => {
      it('should track events and generate analytics', async () => {
        // Track events
        await request(app)
          .post('/api/analytics/events')
          .set('Authorization', `Bearer ${userToken}`)
          .send({
            name: 'page_view',
            properties: {
              page: '/dashboard',
              duration: 5000,
            },
          });
        
        await request(app)
          .post('/api/analytics/events')
          .set('Authorization', `Bearer ${userToken}`)
          .send({
            name: 'button_click',
            properties: {
              button: 'submit',
              form: 'profile',
            },
          });
        
        // Query analytics
        const analyticsRes = await request(app)
          .get('/api/analytics/events')
          .set('Authorization', `Bearer ${adminToken}`)
          .query({
            startDate: new Date(Date.now() - 86400000).toISOString(),
            endDate: new Date().toISOString(),
            event: 'page_view',
          });
        
        expect(analyticsRes.status).toBe(200);
        expect(analyticsRes.body.events.length).toBeGreaterThan(0);
        
        // Generate report
        const reportRes = await request(app)
          .post('/api/analytics/reports')
          .set('Authorization', `Bearer ${adminToken}`)
          .send({
            name: 'User Activity Report',
            type: 'activity',
            dateRange: 'last_7_days',
          });
        
        expect(reportRes.status).toBe(200);
        expect(reportRes.body).toHaveProperty('data');
        expect(reportRes.body).toHaveProperty('insights');
      });

      it('should perform funnel analysis', async () => {
        // Create funnel
        const funnelRes = await request(app)
          .post('/api/analytics/funnels')
          .set('Authorization', `Bearer ${adminToken}`)
          .send({
            name: 'Onboarding Funnel',
            steps: [
              { name: 'Sign Up', event: 'user.created' },
              { name: 'Verify Email', event: 'email.verified' },
              { name: 'Complete Profile', event: 'profile.completed' },
              { name: 'First Action', event: 'first.action' },
            ],
          });
        
        expect(funnelRes.status).toBe(200);
        const funnelId = funnelRes.body.id;
        
        // Get funnel analytics
        const analysisRes = await request(app)
          .get(`/api/analytics/funnels/${funnelId}/analysis`)
          .set('Authorization', `Bearer ${adminToken}`)
          .query({
            dateRange: 'last_30_days',
          });
        
        expect(analysisRes.status).toBe(200);
        expect(analysisRes.body).toHaveProperty('conversionRate');
        expect(analysisRes.body).toHaveProperty('dropoffPoints');
      });
    });

    describe('Performance Optimization', () => {
      it('should use caching effectively', async () => {
        // First request (cache miss)
        const start1 = Date.now();
        const res1 = await request(app)
          .get('/api/users')
          .set('Authorization', `Bearer ${userToken}`);
        const time1 = Date.now() - start1;
        
        expect(res1.status).toBe(200);
        expect(res1.headers['x-cache']).toBe('miss');
        
        // Second request (cache hit)
        const start2 = Date.now();
        const res2 = await request(app)
          .get('/api/users')
          .set('Authorization', `Bearer ${userToken}`);
        const time2 = Date.now() - start2;
        
        expect(res2.status).toBe(200);
        expect(res2.headers['x-cache']).toBe('hit');
        expect(time2).toBeLessThan(time1 * 0.5); // Should be much faster
      });

      it('should optimize database queries', async () => {
        // Request with query optimization hints
        const res = await request(app)
          .get('/api/organizations/' + organizationId + '/members')
          .set('Authorization', `Bearer ${adminToken}`)
          .query({
            include: 'teams,profile',
            optimize: true,
          });
        
        expect(res.status).toBe(200);
        expect(res.headers['x-query-optimized']).toBe('true');
        expect(res.headers['x-query-count']).toBe('1'); // Single optimized query
      });
    });
  });

  describe('End-to-End User Journey', () => {
    it('should complete full user lifecycle', async () => {
      const userEmail = 'lifecycle@test.com';
      
      // 1. User signs up
      const signupRes = await request(app)
        .post('/api/auth/register')
        .send({
          email: userEmail,
          password: 'LifecyclePass123!',
          organizationId,
        });
      
      expect(signupRes.status).toBe(200);
      const newUserId = signupRes.body.user.id;
      const newUserToken = signupRes.body.token;
      
      // 2. User verifies email
      const verifyRes = await request(app)
        .post('/api/auth/verify-email')
        .send({
          token: 'test-verification-token', // Test environment accepts this
        });
      
      expect(verifyRes.status).toBe(200);
      
      // 3. User sets up MFA
      const mfaRes = await request(app)
        .post('/api/mfa/totp/setup')
        .set('Authorization', `Bearer ${newUserToken}`);
      
      expect(mfaRes.status).toBe(200);
      
      // 4. User completes profile
      const profileRes = await request(app)
        .put('/api/users/profile')
        .set('Authorization', `Bearer ${newUserToken}`)
        .send({
          displayName: 'Lifecycle User',
          bio: 'Testing the full lifecycle',
        });
      
      expect(profileRes.status).toBe(200);
      
      // 5. User performs actions (tracked for analytics)
      await request(app)
        .post('/api/analytics/events')
        .set('Authorization', `Bearer ${newUserToken}`)
        .send({
          name: 'first.action',
          properties: { type: 'profile_update' },
        });
      
      // 6. Admin reviews user activity
      const activityRes = await request(app)
        .get(`/api/users/${newUserId}/activity`)
        .set('Authorization', `Bearer ${adminToken}`);
      
      expect(activityRes.status).toBe(200);
      expect(activityRes.body.events.length).toBeGreaterThan(0);
      
      // 7. User is added to a team
      const teamRes = await request(app)
        .post(`/api/organizations/${organizationId}/members/${newUserId}/teams`)
        .set('Authorization', `Bearer ${adminToken}`)
        .send({ teamId: 'product' });
      
      expect(teamRes.status).toBe(200);
      
      // 8. Check complete user state
      const finalStateRes = await request(app)
        .get('/api/auth/me')
        .set('Authorization', `Bearer ${newUserToken}`);
      
      expect(finalStateRes.status).toBe(200);
      expect(finalStateRes.body.email).toBe(userEmail);
      expect(finalStateRes.body.emailVerified).toBe(true);
      expect(finalStateRes.body.mfaEnabled).toBe(true);
      expect(finalStateRes.body.profile.displayName).toBe('Lifecycle User');
      expect(finalStateRes.body.teams).toContain('product');
    });
  });

  describe('Security & Compliance', () => {
    it('should enforce security policies', async () => {
      // Test password policy
      const weakPasswordRes = await request(app)
        .post('/api/auth/register')
        .send({
          email: 'weak@test.com',
          password: '123456',
          organizationId,
        });
      
      expect(weakPasswordRes.status).toBe(400);
      expect(weakPasswordRes.body.error).toContain('password');
      
      // Test SQL injection protection
      const sqlInjectionRes = await request(app)
        .get('/api/users')
        .set('Authorization', `Bearer ${adminToken}`)
        .query({
          filter: "'; DROP TABLE users; --",
        });
      
      expect(sqlInjectionRes.status).toBe(400);
      
      // Test XSS protection
      const xssRes = await request(app)
        .put('/api/users/profile')
        .set('Authorization', `Bearer ${userToken}`)
        .send({
          displayName: '<script>alert("XSS")</script>',
        });
      
      expect(xssRes.status).toBe(400);
      expect(xssRes.body.error).toContain('invalid');
      
      // Test CORS
      const corsRes = await request(app)
        .get('/api/users')
        .set('Origin', 'https://evil.com')
        .set('Authorization', `Bearer ${userToken}`);
      
      expect(corsRes.headers['access-control-allow-origin']).not.toBe('https://evil.com');
    });

    it('should handle rate limiting and DDoS protection', async () => {
      const requests = [];
      
      // Simulate rapid requests from same IP
      for (let i = 0; i < 100; i++) {
        requests.push(
          request(app)
            .get('/api/auth/me')
            .set('Authorization', `Bearer ${userToken}`)
            .set('X-Forwarded-For', '192.168.1.1')
        );
      }
      
      const responses = await Promise.all(requests);
      const blocked = responses.filter(r => r.status === 429);
      
      expect(blocked.length).toBeGreaterThan(50); // Most should be blocked
      
      // Check if IP is temporarily blocked
      const blockedRes = await request(app)
        .get('/api/health')
        .set('X-Forwarded-For', '192.168.1.1');
      
      expect(blockedRes.status).toBe(429);
    });
  });

  describe('Platform Health & Monitoring', () => {
    it('should provide health endpoints', async () => {
      const healthRes = await request(app).get('/api/health');
      
      expect(healthRes.status).toBe(200);
      expect(healthRes.body).toHaveProperty('status', 'healthy');
      expect(healthRes.body).toHaveProperty('services');
      expect(healthRes.body.services).toHaveProperty('database', 'connected');
      expect(healthRes.body.services).toHaveProperty('redis', 'connected');
      expect(healthRes.body.services).toHaveProperty('websocket', 'running');
    });

    it('should provide metrics endpoint', async () => {
      const metricsRes = await request(app)
        .get('/api/metrics')
        .set('Authorization', `Bearer ${adminToken}`);
      
      expect(metricsRes.status).toBe(200);
      expect(metricsRes.body).toHaveProperty('cpu');
      expect(metricsRes.body).toHaveProperty('memory');
      expect(metricsRes.body).toHaveProperty('requests');
      expect(metricsRes.body).toHaveProperty('activeUsers');
      expect(metricsRes.body).toHaveProperty('responseTime');
    });
  });
});