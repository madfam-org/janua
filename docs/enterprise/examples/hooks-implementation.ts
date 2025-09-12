/**
 * Plinto Enterprise Hooks & Events Implementation Examples
 * 
 * This file demonstrates real-world implementations of Plinto's
 * extensibility framework for enterprise use cases.
 */

import { PlintoClient, PlintoHooks, PlintoEvents } from '@plinto/js';
import { WebhookClient } from '@plinto/webhooks';
import { ComplianceLogger } from '@plinto/compliance';

// ============================================
// 1. CUSTOM AUTHENTICATION FLOW WITH HOOKS
// ============================================

/**
 * Enterprise authentication with custom validation and claims
 */
class EnterpriseAuthFlow {
  private plinto: PlintoClient;
  
  constructor() {
    this.plinto = new PlintoClient({
      appId: process.env.PLINTO_APP_ID!,
      hooks: this.configureHooks(),
    });
  }

  private configureHooks(): PlintoHooks {
    return {
      // Pre-authentication hook for custom validation
      beforeAuthentication: async (context) => {
        // Check if user is from allowed domain
        const domain = context.email.split('@')[1];
        if (!this.isAllowedDomain(domain)) {
          throw new Error('DOMAIN_NOT_ALLOWED');
        }

        // Check for IP-based restrictions
        if (await this.isIPBlocked(context.ipAddress)) {
          throw new Error('IP_BLOCKED');
        }

        // Add risk score
        context.metadata.riskScore = await this.calculateRiskScore(context);
        
        return context;
      },

      // Post-authentication hook for custom claims
      afterAuthentication: async (context) => {
        // Add custom claims to JWT
        context.claims.department = await this.getUserDepartment(context.user.id);
        context.claims.permissions = await this.getUserPermissions(context.user.id);
        context.claims.dataClassification = 'confidential';
        
        // Log for compliance
        await this.logAuthentication(context);
        
        return context;
      },

      // Token generation hook
      beforeTokenGeneration: async (context) => {
        // Add enterprise-specific token claims
        context.token.aud = ['api.company.com', 'admin.company.com'];
        context.token.azp = context.application.clientId;
        
        // Set shorter expiry for sensitive roles
        if (context.user.roles.includes('admin')) {
          context.token.exp = Math.floor(Date.now() / 1000) + (15 * 60); // 15 minutes
        }
        
        return context;
      },

      // Session creation hook
      afterSessionCreation: async (context) => {
        // Trigger downstream systems
        await this.notifySecurityTeam(context);
        await this.provisionResources(context.user);
        
        return context;
      }
    };
  }

  private async calculateRiskScore(context: any): Promise<number> {
    let score = 0;
    
    // Location-based risk
    const knownLocations = await this.getKnownLocations(context.user.id);
    if (!knownLocations.includes(context.location.country)) {
      score += 30;
    }
    
    // Time-based risk
    const hour = new Date().getHours();
    if (hour < 6 || hour > 22) {
      score += 20;
    }
    
    // Device trust
    if (!context.device.trusted) {
      score += 25;
    }
    
    // Velocity check
    const recentLogins = await this.getRecentLogins(context.user.id);
    if (recentLogins.length > 5) {
      score += 25;
    }
    
    return Math.min(score, 100);
  }

  private isAllowedDomain(domain: string): boolean {
    const allowedDomains = ['company.com', 'subsidiary.com', 'partner.net'];
    return allowedDomains.includes(domain);
  }

  private async isIPBlocked(ip: string): Promise<boolean> {
    // Check against blocklist
    const blocklist = await this.getIPBlocklist();
    return blocklist.includes(ip);
  }

  private async getUserDepartment(userId: string): Promise<string> {
    // Fetch from HR system
    const response = await fetch(`https://hr.company.com/api/users/${userId}/department`);
    const data = await response.json();
    return data.department;
  }

  private async getUserPermissions(userId: string): Promise<string[]> {
    // Fetch from permission service
    const response = await fetch(`https://permissions.company.com/api/users/${userId}`);
    const data = await response.json();
    return data.permissions;
  }

  private async logAuthentication(context: any): Promise<void> {
    await ComplianceLogger.log({
      event: 'authentication',
      userId: context.user.id,
      email: context.user.email,
      ip: context.ipAddress,
      timestamp: new Date().toISOString(),
      riskScore: context.metadata.riskScore,
      success: true
    });
  }

  private async notifySecurityTeam(context: any): Promise<void> {
    if (context.metadata.riskScore > 70) {
      await fetch('https://security.company.com/api/alerts', {
        method: 'POST',
        body: JSON.stringify({
          type: 'HIGH_RISK_LOGIN',
          user: context.user.email,
          riskScore: context.metadata.riskScore,
          location: context.location
        })
      });
    }
  }

  private async provisionResources(user: any): Promise<void> {
    // Provision cloud resources based on role
    if (user.roles.includes('developer')) {
      await this.provisionDeveloperResources(user);
    }
  }

  private async provisionDeveloperResources(user: any): Promise<void> {
    // Create cloud resources
    await fetch('https://cloud.company.com/api/provision', {
      method: 'POST',
      body: JSON.stringify({
        userId: user.id,
        resources: ['git-repo', 'ci-pipeline', 'dev-environment']
      })
    });
  }

  private async getKnownLocations(userId: string): Promise<string[]> {
    // Implementation
    return ['US', 'UK', 'DE'];
  }

  private async getRecentLogins(userId: string): Promise<any[]> {
    // Implementation
    return [];
  }

  private async getIPBlocklist(): Promise<string[]> {
    // Implementation
    return [];
  }
}

// ============================================
// 2. EVENT-DRIVEN WORKFLOW AUTOMATION
// ============================================

/**
 * Automated workflows triggered by Plinto events
 */
class WorkflowAutomation {
  private events: PlintoEvents;
  private webhooks: WebhookClient;

  constructor() {
    this.events = new PlintoEvents({
      appId: process.env.PLINTO_APP_ID!
    });
    
    this.webhooks = new WebhookClient({
      signingSecret: process.env.WEBHOOK_SECRET!
    });

    this.registerWorkflows();
  }

  private registerWorkflows(): void {
    // New user onboarding workflow
    this.events.on('user.created', async (event) => {
      await this.onboardNewUser(event.data);
    });

    // Suspicious activity workflow
    this.events.on('security.suspicious.activity', async (event) => {
      await this.handleSuspiciousActivity(event.data);
    });

    // Organization changes workflow
    this.events.on('org.member.role.changed', async (event) => {
      await this.syncPermissions(event.data);
    });

    // Compliance workflow
    this.events.on('user.data.export.requested', async (event) => {
      await this.handleGDPRRequest(event.data);
    });

    // Password reset workflow
    this.events.on('auth.password.reset.requested', async (event) => {
      await this.validatePasswordReset(event.data);
    });
  }

  private async onboardNewUser(user: any): Promise<void> {
    const workflow = [
      this.sendWelcomeEmail(user),
      this.createJiraTicket(user),
      this.addToSlack(user),
      this.scheduleTraining(user),
      this.provisionAccounts(user)
    ];

    await Promise.all(workflow);
  }

  private async handleSuspiciousActivity(event: any): Promise<void> {
    // Immediate actions
    if (event.riskScore > 90) {
      await this.lockAccount(event.userId);
      await this.revokeAllSessions(event.userId);
    }

    // Notifications
    await this.notifySecurityTeam(event);
    await this.createSecurityIncident(event);

    // Investigation
    await this.collectForensics(event);
  }

  private async syncPermissions(event: any): Promise<void> {
    // Sync with external systems
    const systems = [
      this.syncWithActiveDirectory(event),
      this.syncWithGoogleWorkspace(event),
      this.syncWithAWS(event),
      this.syncWithGitHub(event)
    ];

    await Promise.all(systems);
  }

  private async handleGDPRRequest(request: any): Promise<void> {
    // Generate data export
    const exportData = await this.collectUserData(request.userId);
    
    // Encrypt export
    const encrypted = await this.encryptData(exportData);
    
    // Store securely
    const url = await this.storeExport(encrypted);
    
    // Notify user
    await this.sendExportLink(request.userId, url);
    
    // Log for compliance
    await this.logGDPRAction(request);
  }

  private async validatePasswordReset(request: any): Promise<void> {
    // Check for suspicious patterns
    const recentResets = await this.getRecentPasswordResets(request.userId);
    
    if (recentResets.length > 3) {
      // Flag as suspicious
      await this.flagSuspiciousActivity(request.userId, 'EXCESSIVE_PASSWORD_RESETS');
      
      // Require additional verification
      await this.requireAdditionalVerification(request.userId);
    }
  }

  // Helper methods (implementations would go here)
  private async sendWelcomeEmail(user: any): Promise<void> { /* ... */ }
  private async createJiraTicket(user: any): Promise<void> { /* ... */ }
  private async addToSlack(user: any): Promise<void> { /* ... */ }
  private async scheduleTraining(user: any): Promise<void> { /* ... */ }
  private async provisionAccounts(user: any): Promise<void> { /* ... */ }
  private async lockAccount(userId: string): Promise<void> { /* ... */ }
  private async revokeAllSessions(userId: string): Promise<void> { /* ... */ }
  private async notifySecurityTeam(event: any): Promise<void> { /* ... */ }
  private async createSecurityIncident(event: any): Promise<void> { /* ... */ }
  private async collectForensics(event: any): Promise<void> { /* ... */ }
  private async syncWithActiveDirectory(event: any): Promise<void> { /* ... */ }
  private async syncWithGoogleWorkspace(event: any): Promise<void> { /* ... */ }
  private async syncWithAWS(event: any): Promise<void> { /* ... */ }
  private async syncWithGitHub(event: any): Promise<void> { /* ... */ }
  private async collectUserData(userId: string): Promise<any> { /* ... */ }
  private async encryptData(data: any): Promise<any> { /* ... */ }
  private async storeExport(data: any): Promise<string> { return ''; }
  private async sendExportLink(userId: string, url: string): Promise<void> { /* ... */ }
  private async logGDPRAction(request: any): Promise<void> { /* ... */ }
  private async getRecentPasswordResets(userId: string): Promise<any[]> { return []; }
  private async flagSuspiciousActivity(userId: string, reason: string): Promise<void> { /* ... */ }
  private async requireAdditionalVerification(userId: string): Promise<void> { /* ... */ }
}

// ============================================
// 3. CUSTOM CLAIMS AND TOKEN ENRICHMENT
// ============================================

/**
 * Advanced token customization for enterprise scenarios
 */
class TokenEnrichment {
  static async enrichToken(baseToken: any, user: any): Promise<any> {
    const enrichedToken = { ...baseToken };

    // Add organizational hierarchy
    enrichedToken.org_hierarchy = await this.getOrgHierarchy(user);

    // Add cost center for billing
    enrichedToken.cost_center = await this.getCostCenter(user);

    // Add data access levels
    enrichedToken.data_access = {
      pii: user.roles.includes('hr') || user.roles.includes('admin'),
      financial: user.roles.includes('finance') || user.roles.includes('executive'),
      technical: user.roles.includes('engineering'),
      customer: user.roles.includes('support') || user.roles.includes('sales')
    };

    // Add compliance flags
    enrichedToken.compliance = {
      gdpr_consent: user.gdprConsent,
      data_residency: user.dataResidency,
      export_control: await this.checkExportControl(user)
    };

    // Add temporary elevation
    if (user.temporaryElevation) {
      enrichedToken.elevated = {
        until: user.temporaryElevation.expiresAt,
        reason: user.temporaryElevation.reason,
        approver: user.temporaryElevation.approvedBy
      };
    }

    return enrichedToken;
  }

  private static async getOrgHierarchy(user: any): Promise<any> {
    return {
      company: 'ACME Corp',
      division: 'Technology',
      department: 'Engineering',
      team: 'Platform',
      manager: 'manager_123'
    };
  }

  private static async getCostCenter(user: any): Promise<string> {
    return 'CC-TECH-001';
  }

  private static async checkExportControl(user: any): Promise<boolean> {
    // Check if user is subject to export control regulations
    const restrictedCountries = ['IR', 'KP', 'SY'];
    return !restrictedCountries.includes(user.location.country);
  }
}

// ============================================
// 4. WEBHOOK ORCHESTRATION
// ============================================

/**
 * Enterprise webhook management with retry and DLQ
 */
class WebhookOrchestrator {
  private webhooks: Map<string, WebhookConfig> = new Map();

  constructor() {
    this.registerWebhooks();
  }

  private registerWebhooks(): void {
    // SIEM integration
    this.webhooks.set('siem', {
      url: 'https://siem.company.com/api/events',
      events: ['auth.*', 'security.*', 'user.deleted'],
      headers: {
        'X-API-Key': process.env.SIEM_API_KEY!
      },
      retry: {
        attempts: 5,
        backoff: 'exponential',
        maxDelay: 300000 // 5 minutes
      },
      transform: this.transformForSIEM
    });

    // HR system integration
    this.webhooks.set('hr', {
      url: 'https://hr.company.com/api/webhooks',
      events: ['user.created', 'user.updated', 'org.member.*'],
      headers: {
        'Authorization': `Bearer ${process.env.HR_TOKEN}`
      },
      retry: {
        attempts: 3,
        backoff: 'linear',
        delay: 5000
      },
      transform: this.transformForHR
    });

    // Billing system integration
    this.webhooks.set('billing', {
      url: 'https://billing.company.com/api/usage',
      events: ['auth.login.success', 'org.created', 'user.created'],
      headers: {
        'X-Billing-Key': process.env.BILLING_KEY!
      },
      retry: {
        attempts: 10,
        backoff: 'exponential',
        maxDelay: 3600000 // 1 hour
      },
      transform: this.transformForBilling
    });
  }

  private transformForSIEM(event: any): any {
    return {
      timestamp: event.timestamp,
      severity: this.calculateSeverity(event),
      category: 'authentication',
      source_ip: event.ip,
      user_id: event.userId,
      action: event.type,
      outcome: event.success ? 'success' : 'failure',
      raw: JSON.stringify(event)
    };
  }

  private transformForHR(event: any): any {
    return {
      employeeId: event.user?.employeeId,
      email: event.user?.email,
      department: event.user?.department,
      action: event.type,
      timestamp: event.timestamp
    };
  }

  private transformForBilling(event: any): any {
    return {
      customerId: event.organizationId,
      userId: event.userId,
      event: event.type,
      timestamp: event.timestamp,
      metadata: {
        plan: event.organization?.plan,
        seats: event.organization?.seats
      }
    };
  }

  private calculateSeverity(event: any): string {
    if (event.type.includes('breach') || event.type.includes('suspicious')) {
      return 'critical';
    }
    if (event.type.includes('failed')) {
      return 'warning';
    }
    return 'info';
  }

  public async processEvent(event: any): Promise<void> {
    const promises = [];

    for (const [name, config] of this.webhooks) {
      if (this.shouldSendToWebhook(event.type, config.events)) {
        promises.push(this.sendWithRetry(event, config));
      }
    }

    await Promise.allSettled(promises);
  }

  private shouldSendToWebhook(eventType: string, patterns: string[]): boolean {
    return patterns.some(pattern => {
      if (pattern.endsWith('*')) {
        return eventType.startsWith(pattern.slice(0, -1));
      }
      return eventType === pattern;
    });
  }

  private async sendWithRetry(event: any, config: WebhookConfig): Promise<void> {
    const transformed = config.transform ? config.transform(event) : event;
    let lastError: any;

    for (let attempt = 0; attempt < config.retry.attempts; attempt++) {
      try {
        const response = await fetch(config.url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...config.headers
          },
          body: JSON.stringify(transformed)
        });

        if (response.ok) {
          return;
        }

        lastError = new Error(`HTTP ${response.status}`);
      } catch (error) {
        lastError = error;
      }

      // Calculate delay
      const delay = this.calculateDelay(attempt, config.retry);
      await new Promise(resolve => setTimeout(resolve, delay));
    }

    // Send to DLQ after all retries failed
    await this.sendToDeadLetterQueue(event, config, lastError);
  }

  private calculateDelay(attempt: number, retry: any): number {
    if (retry.backoff === 'exponential') {
      const delay = Math.min(1000 * Math.pow(2, attempt), retry.maxDelay || 300000);
      return delay;
    }
    return retry.delay || 5000;
  }

  private async sendToDeadLetterQueue(event: any, config: WebhookConfig, error: any): Promise<void> {
    await fetch('https://dlq.company.com/api/failed-webhooks', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        event,
        webhook: config.url,
        error: error.message,
        timestamp: new Date().toISOString()
      })
    });
  }
}

interface WebhookConfig {
  url: string;
  events: string[];
  headers: Record<string, string>;
  retry: {
    attempts: number;
    backoff: 'linear' | 'exponential';
    delay?: number;
    maxDelay?: number;
  };
  transform?: (event: any) => any;
}

// Export for use in applications
export {
  EnterpriseAuthFlow,
  WorkflowAutomation,
  TokenEnrichment,
  WebhookOrchestrator
};