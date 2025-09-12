# Enterprise SSO Integration Guide

## Overview

Plinto provides comprehensive Single Sign-On (SSO) support for enterprise organizations, enabling seamless integration with existing identity providers while maintaining security and compliance requirements.

## Supported Protocols

### SAML 2.0
Full support for Security Assertion Markup Language (SAML) 2.0 with:
- Service Provider (SP) initiated flows
- Identity Provider (IdP) initiated flows
- Just-In-Time (JIT) provisioning
- Attribute mapping and transformation
- Encrypted assertions support

### OpenID Connect (OIDC)
Modern OAuth 2.0-based authentication with:
- Authorization Code flow with PKCE
- Implicit flow (deprecated but supported)
- Hybrid flow for specific enterprise needs
- Dynamic client registration
- Discovery endpoint support

### OAuth 2.0
Flexible OAuth integration supporting:
- Custom OAuth providers
- Social login providers (Google, GitHub, Microsoft)
- Token introspection
- Refresh token rotation
- Fine-grained scopes

## Implementation Architecture

```typescript
// Enterprise SSO Configuration
interface SSOConfiguration {
  id: string;
  organizationId: string;
  protocol: 'saml' | 'oidc' | 'oauth2';
  enabled: boolean;
  
  // Protocol-specific configuration
  samlConfig?: SAMLConfiguration;
  oidcConfig?: OIDCConfiguration;
  oauth2Config?: OAuth2Configuration;
  
  // Common settings
  jitProvisioning: boolean;
  defaultRole: string;
  attributeMapping: AttributeMap;
  allowedDomains: string[];
  
  // Security settings
  mfaRequired: boolean;
  sessionTimeout: number;
  maxConcurrentSessions: number;
}

interface SAMLConfiguration {
  idpMetadataUrl?: string;
  idpMetadataXml?: string;
  ssoUrl: string;
  sloUrl?: string;
  certificate: string;
  
  // SP Configuration
  spEntityId: string;
  acsUrl: string;
  
  // Advanced settings
  signRequest: boolean;
  encryptAssertion: boolean;
  authnContextClass: string[];
  attributeStatements: AttributeStatement[];
}

interface OIDCConfiguration {
  issuer: string;
  clientId: string;
  clientSecret?: string; // For confidential clients
  discoveryUrl?: string;
  
  // Endpoints (if discovery not used)
  authorizationUrl?: string;
  tokenUrl?: string;
  userInfoUrl?: string;
  jwksUrl?: string;
  
  // Scopes and claims
  scopes: string[];
  requestedClaims?: ClaimRequest[];
  
  // Advanced settings
  responseType: 'code' | 'id_token' | 'token';
  responseMode: 'query' | 'fragment' | 'form_post';
  pkceRequired: boolean;
}
```

## SAML Integration

### 1. Configuration Setup

```typescript
import { PlintoSSO } from '@plinto/enterprise';

const ssoClient = new PlintoSSO({
  apiKey: process.env.PLINTO_API_KEY,
  organizationId: 'org_123'
});

// Configure SAML provider
await ssoClient.configureSAML({
  idpMetadataUrl: 'https://idp.example.com/metadata',
  spEntityId: 'https://app.example.com',
  acsUrl: 'https://app.example.com/sso/saml/callback',
  
  // Attribute mapping
  attributeMapping: {
    email: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress',
    firstName: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname',
    lastName: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname',
    groups: 'http://schemas.microsoft.com/ws/2008/06/identity/claims/groups'
  },
  
  // JIT provisioning
  jitProvisioning: true,
  defaultRole: 'member',
  
  // Security
  signRequest: true,
  encryptAssertion: true
});
```

### 2. SP-Initiated Flow

```typescript
// Generate SAML AuthnRequest
app.get('/sso/saml/login', async (req, res) => {
  const { redirectUrl, samlRequest } = await ssoClient.saml.createAuthRequest({
    relayState: req.query.returnTo || '/',
    forceAuthn: false,
    isPassive: false
  });
  
  // Redirect to IdP
  res.redirect(redirectUrl);
});

// Handle SAML Response
app.post('/sso/saml/callback', async (req, res) => {
  try {
    const { user, session, attributes } = await ssoClient.saml.validateResponse({
      samlResponse: req.body.SAMLResponse,
      relayState: req.body.RelayState
    });
    
    // Create session
    req.session.user = user;
    req.session.ssoProvider = 'saml';
    
    // Redirect to application
    res.redirect(req.body.RelayState || '/dashboard');
  } catch (error) {
    console.error('SAML validation failed:', error);
    res.redirect('/login?error=sso_failed');
  }
});
```

### 3. IdP-Initiated Flow

```typescript
app.post('/sso/saml/idp-initiated', async (req, res) => {
  const { user, session } = await ssoClient.saml.handleIdpInitiated({
    samlResponse: req.body.SAMLResponse,
    
    // Validate IdP is allowed
    validateIdp: true,
    allowedIdps: ['https://idp.example.com']
  });
  
  // Create session and redirect
  req.session.user = user;
  res.redirect('/dashboard');
});
```

## OIDC Integration

### 1. Configuration

```typescript
// Configure OIDC provider
await ssoClient.configureOIDC({
  issuer: 'https://accounts.google.com',
  clientId: process.env.GOOGLE_CLIENT_ID,
  clientSecret: process.env.GOOGLE_CLIENT_SECRET,
  
  scopes: ['openid', 'profile', 'email'],
  
  // Use discovery
  discoveryUrl: 'https://accounts.google.com/.well-known/openid-configuration',
  
  // Enable PKCE
  pkceRequired: true,
  
  // Attribute mapping
  attributeMapping: {
    email: 'email',
    firstName: 'given_name',
    lastName: 'family_name',
    picture: 'picture'
  }
});
```

### 2. Authorization Flow

```typescript
// Initiate OIDC flow
app.get('/sso/oidc/login', async (req, res) => {
  const { authUrl, state, codeVerifier } = await ssoClient.oidc.createAuthRequest({
    redirectUri: 'https://app.example.com/sso/oidc/callback',
    scope: 'openid profile email',
    prompt: 'select_account',
    
    // Store for callback validation
    state: crypto.randomBytes(16).toString('hex'),
    nonce: crypto.randomBytes(16).toString('hex')
  });
  
  // Store state and code verifier in session
  req.session.oidcState = state;
  req.session.codeVerifier = codeVerifier;
  
  res.redirect(authUrl);
});

// Handle callback
app.get('/sso/oidc/callback', async (req, res) => {
  // Validate state
  if (req.query.state !== req.session.oidcState) {
    return res.status(400).send('Invalid state');
  }
  
  // Exchange code for tokens
  const { tokens, user } = await ssoClient.oidc.handleCallback({
    code: req.query.code,
    redirectUri: 'https://app.example.com/sso/oidc/callback',
    codeVerifier: req.session.codeVerifier
  });
  
  // Validate ID token
  const claims = await ssoClient.oidc.validateIdToken(tokens.id_token);
  
  // Create user session
  req.session.user = user;
  req.session.tokens = tokens;
  
  res.redirect('/dashboard');
});
```

## Just-In-Time (JIT) Provisioning

```typescript
class JITProvisioning {
  async provisionUser(ssoUser: SSOUser, organization: Organization) {
    // Check if user exists
    let user = await this.findUserByEmail(ssoUser.email);
    
    if (!user) {
      // Create new user
      user = await this.createUser({
        email: ssoUser.email,
        firstName: ssoUser.attributes.firstName,
        lastName: ssoUser.attributes.lastName,
        emailVerified: true,
        
        // SSO metadata
        ssoProvider: ssoUser.provider,
        ssoId: ssoUser.providerId,
        
        // Organization assignment
        organizationId: organization.id,
        role: this.determineRole(ssoUser.attributes.groups)
      });
      
      // Trigger provisioning webhook
      await this.webhooks.send('user.sso.provisioned', {
        user,
        provider: ssoUser.provider,
        organization
      });
    } else {
      // Update existing user
      await this.updateUser(user.id, {
        lastSSOLogin: new Date(),
        ssoAttributes: ssoUser.attributes
      });
    }
    
    // Sync group memberships
    await this.syncGroups(user, ssoUser.attributes.groups);
    
    return user;
  }
  
  private determineRole(groups: string[]): string {
    // Map SSO groups to application roles
    const roleMapping = {
      'admins': 'admin',
      'developers': 'developer',
      'users': 'member'
    };
    
    for (const [group, role] of Object.entries(roleMapping)) {
      if (groups.includes(group)) {
        return role;
      }
    }
    
    return 'member'; // Default role
  }
}
```

## Directory Sync (SCIM)

```typescript
// SCIM 2.0 Implementation
class SCIMProvider {
  // User provisioning
  async createUser(scimUser: SCIMUser) {
    const user = await this.userService.create({
      userName: scimUser.userName,
      name: scimUser.name,
      emails: scimUser.emails,
      active: scimUser.active,
      externalId: scimUser.externalId
    });
    
    return this.toSCIMResponse(user);
  }
  
  // Group management
  async syncGroups(scimGroup: SCIMGroup) {
    const group = await this.groupService.upsert({
      displayName: scimGroup.displayName,
      members: scimGroup.members,
      externalId: scimGroup.externalId
    });
    
    // Update user memberships
    await this.syncMemberships(group, scimGroup.members);
    
    return this.toSCIMGroupResponse(group);
  }
  
  // Bulk operations
  async bulkOperation(operations: SCIMBulkOp[]) {
    const results = [];
    
    for (const op of operations) {
      try {
        const result = await this.executeOperation(op);
        results.push({ status: 'success', result });
      } catch (error) {
        results.push({ status: 'failed', error: error.message });
      }
    }
    
    return results;
  }
}
```

## Security Considerations

### 1. Certificate Management

```typescript
class CertificateManager {
  async rotateCertificates(organizationId: string) {
    // Generate new certificate
    const newCert = await this.generateCertificate();
    
    // Update SSO configuration
    await this.ssoConfig.update(organizationId, {
      certificates: {
        primary: newCert,
        secondary: this.getCurrentCert(), // Keep old cert for rotation
        rotationDate: new Date()
      }
    });
    
    // Schedule old certificate removal
    await this.scheduler.schedule('remove-old-cert', {
      date: addDays(new Date(), 30),
      organizationId
    });
  }
  
  async validateCertificate(cert: string): Promise<boolean> {
    // Check certificate validity
    const parsed = this.parseCertificate(cert);
    
    // Validate expiration
    if (parsed.notAfter < new Date()) {
      throw new Error('Certificate expired');
    }
    
    // Validate signature
    return this.verifyCertificateChain(parsed);
  }
}
```

### 2. Session Management

```typescript
class SSOSessionManager {
  async createSession(user: User, ssoContext: SSOContext) {
    // Check concurrent sessions
    const activeSessions = await this.getActiveSessions(user.id);
    
    if (activeSessions.length >= ssoContext.maxConcurrentSessions) {
      // Terminate oldest session
      await this.terminateSession(activeSessions[0].id);
    }
    
    // Create new session
    const session = await this.sessions.create({
      userId: user.id,
      organizationId: ssoContext.organizationId,
      provider: ssoContext.provider,
      
      // Security settings
      ipAddress: ssoContext.ipAddress,
      userAgent: ssoContext.userAgent,
      
      // Timeout configuration
      expiresAt: addMinutes(new Date(), ssoContext.sessionTimeout),
      absoluteTimeout: addHours(new Date(), 12),
      
      // MFA status
      mfaVerified: ssoContext.mfaVerified || false
    });
    
    return session;
  }
  
  async validateSession(sessionId: string): Promise<boolean> {
    const session = await this.sessions.get(sessionId);
    
    // Check expiration
    if (session.expiresAt < new Date()) {
      await this.terminateSession(sessionId);
      return false;
    }
    
    // Check absolute timeout
    if (session.absoluteTimeout < new Date()) {
      await this.terminateSession(sessionId);
      return false;
    }
    
    // Extend session
    await this.sessions.update(sessionId, {
      expiresAt: addMinutes(new Date(), session.timeout),
      lastActivity: new Date()
    });
    
    return true;
  }
}
```

## Testing SSO Integration

```typescript
// Integration tests
describe('SSO Integration', () => {
  let ssoClient: PlintoSSO;
  
  beforeEach(() => {
    ssoClient = new PlintoSSO({
      apiKey: 'test-key',
      environment: 'test'
    });
  });
  
  describe('SAML', () => {
    it('should generate valid AuthnRequest', async () => {
      const { samlRequest, redirectUrl } = await ssoClient.saml.createAuthRequest({
        idp: 'test-idp',
        relayState: '/dashboard'
      });
      
      expect(samlRequest).toContain('AuthnRequest');
      expect(redirectUrl).toContain('SAMLRequest=');
    });
    
    it('should validate SAML response', async () => {
      const mockResponse = createMockSAMLResponse();
      
      const { user, attributes } = await ssoClient.saml.validateResponse({
        samlResponse: mockResponse
      });
      
      expect(user.email).toBe('user@example.com');
      expect(attributes.groups).toContain('admins');
    });
  });
  
  describe('OIDC', () => {
    it('should handle authorization flow', async () => {
      const { authUrl, state } = await ssoClient.oidc.createAuthRequest({
        redirectUri: 'http://localhost:3000/callback'
      });
      
      expect(authUrl).toContain('response_type=code');
      expect(authUrl).toContain(`state=${state}`);
    });
    
    it('should validate ID token', async () => {
      const mockToken = createMockIdToken();
      
      const claims = await ssoClient.oidc.validateIdToken(mockToken);
      
      expect(claims.sub).toBeDefined();
      expect(claims.email).toBe('user@example.com');
    });
  });
});
```

## Monitoring and Analytics

```typescript
class SSOAnalytics {
  // Track SSO usage
  async trackLogin(event: SSOLoginEvent) {
    await this.analytics.track({
      event: 'sso.login',
      organizationId: event.organizationId,
      provider: event.provider,
      userId: event.userId,
      
      metadata: {
        jitProvisioned: event.jitProvisioned,
        mfaRequired: event.mfaRequired,
        loginDuration: event.duration,
        
        // Error tracking
        failed: event.failed,
        errorCode: event.errorCode
      }
    });
  }
  
  // Generate reports
  async generateSSOReport(organizationId: string, period: DateRange) {
    const stats = await this.db.query(`
      SELECT 
        provider,
        COUNT(*) as login_count,
        COUNT(DISTINCT user_id) as unique_users,
        AVG(duration) as avg_duration,
        SUM(CASE WHEN failed THEN 1 ELSE 0 END) as failures
      FROM sso_events
      WHERE organization_id = $1
        AND created_at BETWEEN $2 AND $3
      GROUP BY provider
    `, [organizationId, period.start, period.end]);
    
    return {
      period,
      providers: stats,
      
      // Adoption metrics
      ssoAdoptionRate: await this.calculateAdoptionRate(organizationId),
      
      // Security metrics
      mfaEnforcementRate: await this.calculateMFARate(organizationId),
      
      // Performance metrics
      averageLoginTime: stats.reduce((acc, s) => acc + s.avg_duration, 0) / stats.length
    };
  }
}
```

## Migration Guide

### Migrating from Legacy Authentication

```typescript
class SSOmigration {
  async migrateOrganization(orgId: string) {
    // Phase 1: Enable SSO alongside existing auth
    await this.enableDualAuth(orgId);
    
    // Phase 2: Migrate users gradually
    const users = await this.getOrganizationUsers(orgId);
    
    for (const user of users) {
      await this.migrateUser(user, {
        sendNotification: true,
        gracePeriodDays: 30
      });
    }
    
    // Phase 3: Monitor adoption
    await this.monitorAdoption(orgId);
    
    // Phase 4: Disable legacy auth
    await this.scheduleLegacyDisable(orgId, {
      date: addDays(new Date(), 60),
      notifyBeforeDays: 7
    });
  }
  
  private async migrateUser(user: User, options: MigrationOptions) {
    // Link SSO identity
    await this.linkSSOIdentity(user);
    
    // Send migration notification
    if (options.sendNotification) {
      await this.notifications.send(user, 'sso-migration', {
        deadline: addDays(new Date(), options.gracePeriodDays),
        ssoUrl: this.getSSOLoginUrl(user.organizationId)
      });
    }
    
    // Track migration status
    await this.tracking.update(user.id, {
      ssoMigrationStatus: 'pending',
      migrationDeadline: addDays(new Date(), options.gracePeriodDays)
    });
  }
}
```

## Best Practices

### 1. Configuration Management
- Store SSO configurations in version control
- Use environment-specific settings
- Implement configuration validation
- Regular certificate rotation

### 2. Error Handling
- Graceful fallback for SSO failures
- Clear error messages for users
- Detailed logging for debugging
- Automatic retry mechanisms

### 3. Performance Optimization
- Cache IdP metadata
- Implement connection pooling
- Use async processing for JIT provisioning
- Optimize attribute mapping

### 4. Security Hardening
- Enforce HTTPS for all SSO endpoints
- Implement request signing
- Use encrypted assertions
- Regular security audits

### 5. User Experience
- Seamless SSO flow
- Clear provider selection
- Progress indicators
- Mobile-optimized flows

## Troubleshooting

### Common Issues

1. **SAML Assertion Validation Failures**
   - Check certificate validity
   - Verify audience restrictions
   - Validate timestamp windows
   - Review signature algorithms

2. **OIDC Token Validation Errors**
   - Verify JWKS endpoint accessibility
   - Check token expiration
   - Validate issuer claim
   - Review scope requirements

3. **JIT Provisioning Failures**
   - Check attribute mapping
   - Verify required fields
   - Review role assignments
   - Check organization limits

4. **Session Management Issues**
   - Review timeout settings
   - Check concurrent session limits
   - Verify cookie configuration
   - Review CORS settings

## Support

For enterprise SSO support:
- Email: enterprise@plinto.dev
- Documentation: https://docs.plinto.dev/enterprise/sso
- Status: https://status.plinto.dev
- Enterprise Support Portal: https://support.plinto.dev