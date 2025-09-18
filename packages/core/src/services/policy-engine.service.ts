import { EventEmitter } from 'events';
import crypto from 'crypto';

export interface PolicyDocument {
  id: string;
  version: string;
  name: string;
  description?: string;
  package: string; // OPA package name
  rules: PolicyRule[];
  metadata: {
    author: string;
    created_at: Date;
    updated_at: Date;
    tags: string[];
    compliance?: string[];
  };
  active: boolean;
}

export interface PolicyRule {
  name: string;
  description?: string;
  rule: string; // Rego rule
  effect: 'allow' | 'deny';
  conditions?: PolicyCondition[];
  priority?: number;
}

export interface PolicyCondition {
  type: 'attribute' | 'time' | 'location' | 'risk' | 'custom';
  operator: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'not_in' | 'matches' | 'contains';
  field: string;
  value: any;
}

export interface PolicyEvaluationContext {
  subject: {
    id: string;
    type: 'user' | 'service' | 'api_key';
    attributes: Record<string, any>;
    roles?: string[];
    permissions?: string[];
    groups?: string[];
  };
  resource: {
    id?: string;
    type: string;
    attributes: Record<string, any>;
    owner?: string;
    tags?: string[];
  };
  action: string;
  environment: {
    time: Date;
    ip_address?: string;
    user_agent?: string;
    location?: {
      country?: string;
      region?: string;
      city?: string;
    };
    risk_score?: number;
    session_id?: string;
    mfa_verified?: boolean;
  };
  additional_context?: Record<string, any>;
}

export interface PolicyEvaluationResult {
  allowed: boolean;
  reasons: string[];
  matched_policies: string[];
  evaluation_time_ms: number;
  obligations?: PolicyObligation[];
  advice?: PolicyAdvice[];
  risk_score?: number;
}

export interface PolicyObligation {
  id: string;
  type: 'audit' | 'notify' | 'encrypt' | 'redact' | 'custom';
  parameters: Record<string, any>;
  mandatory: boolean;
}

export interface PolicyAdvice {
  id: string;
  type: 'warning' | 'info' | 'recommendation';
  message: string;
  severity: 'low' | 'medium' | 'high';
}

export interface RBACRole {
  id: string;
  name: string;
  description?: string;
  permissions: string[];
  parent_roles?: string[]; // Role inheritance
  conditions?: PolicyCondition[];
  metadata?: Record<string, any>;
}

export interface ABACAttribute {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  description?: string;
  allowed_values?: any[];
  validation_rule?: string;
  source: 'user' | 'resource' | 'environment' | 'external';
}

export class PolicyEngine extends EventEmitter {
  private policies: Map<string, PolicyDocument> = new Map();
  private policyVersions: Map<string, PolicyDocument[]> = new Map();
  private roles: Map<string, RBACRole> = new Map();
  private attributes: Map<string, ABACAttribute> = new Map();
  private evaluationCache: Map<string, PolicyEvaluationResult> = new Map();
  private readonly CACHE_TTL_MS = 60000; // 1 minute

  constructor(
    private readonly config: {
      enableCache?: boolean;
      cacheTTL?: number;
      opaEndpoint?: string; // Optional OPA server endpoint
      evaluationTimeout?: number;
      enablePolicyVersioning?: boolean;
      maxVersionHistory?: number;
    } = {}
  ) {
    super();
    this.initializeDefaultPolicies();
    this.initializeDefaultRoles();
  }

  /**
   * Evaluate a policy decision
   */
  async evaluate(context: PolicyEvaluationContext): Promise<PolicyEvaluationResult> {
    const startTime = Date.now();

    // Check cache
    if (this.config.enableCache) {
      const cacheKey = this.getCacheKey(context);
      const cached = this.evaluationCache.get(cacheKey);
      if (cached && this.isCacheValid(cached, startTime)) {
        return cached;
      }
    }

    try {
      // If OPA server is configured, use it
      if (this.config.opaEndpoint) {
        return await this.evaluateWithOPA(context);
      }

      // Otherwise use internal evaluation
      const result = await this.evaluateInternal(context);
      
      // Cache result
      if (this.config.enableCache) {
        const cacheKey = this.getCacheKey(context);
        this.evaluationCache.set(cacheKey, result);
      }

      // Emit event for monitoring
      this.emit('policy:evaluated', { context, result });

      // Check for high-risk operations
      if (result.risk_score && result.risk_score > 0.7) {
        this.emit('policy:high-risk', { context, result });
      }

      return result;
    } catch (error) {
      this.emit('policy:error', { context, error });
      // Fail closed - deny on error
      return {
        allowed: false,
        reasons: ['Policy evaluation error'],
        matched_policies: [],
        evaluation_time_ms: Date.now() - startTime
      };
    }
  }

  /**
   * Internal policy evaluation
   */
  private async evaluateInternal(context: PolicyEvaluationContext): Promise<PolicyEvaluationResult> {
    const startTime = Date.now();
    const matchedPolicies: string[] = [];
    const reasons: string[] = [];
    const obligations: PolicyObligation[] = [];
    const advice: PolicyAdvice[] = [];
    let allowed = false;

    // 1. Evaluate RBAC policies
    const rbacResult = this.evaluateRBAC(context);
    if (rbacResult.matched) {
      matchedPolicies.push(...rbacResult.policies);
      reasons.push(...rbacResult.reasons);
      allowed = rbacResult.allowed;
    }

    // 2. Evaluate ABAC policies
    const abacResult = this.evaluateABAC(context);
    if (abacResult.matched) {
      matchedPolicies.push(...abacResult.policies);
      reasons.push(...abacResult.reasons);
      // ABAC can override RBAC
      if (abacResult.priority > (rbacResult.priority || 0)) {
        allowed = abacResult.allowed;
      }
    }

    // 3. Evaluate custom policies
    for (const [id, policy] of this.policies) {
      if (!policy.active) continue;

      const policyResult = this.evaluatePolicy(policy, context);
      if (policyResult.matched) {
        matchedPolicies.push(id);
        reasons.push(...policyResult.reasons);
        obligations.push(...(policyResult.obligations || []));
        advice.push(...(policyResult.advice || []));

        // Higher priority policies override
        if (policyResult.effect === 'deny') {
          allowed = false;
          reasons.push(`Denied by policy: ${policy.name}`);
          break; // Deny takes precedence
        } else if (policyResult.effect === 'allow') {
          allowed = true;
        }
      }
    }

    // 4. Apply default deny if no policies matched
    if (matchedPolicies.length === 0) {
      allowed = false;
      reasons.push('No matching policies - default deny');
    }

    // 5. Calculate risk score
    const riskScore = this.calculateRiskScore(context, allowed);

    return {
      allowed,
      reasons,
      matched_policies: matchedPolicies,
      evaluation_time_ms: Date.now() - startTime,
      obligations: obligations.length > 0 ? obligations : undefined,
      advice: advice.length > 0 ? advice : undefined,
      risk_score: riskScore
    };
  }

  /**
   * Evaluate RBAC policies
   */
  private evaluateRBAC(context: PolicyEvaluationContext): {
    matched: boolean;
    allowed: boolean;
    policies: string[];
    reasons: string[];
    priority: number;
  } {
    const policies: string[] = [];
    const reasons: string[] = [];
    let allowed = false;

    if (!context.subject.roles || context.subject.roles.length === 0) {
      return { matched: false, allowed: false, policies: [], reasons: [], priority: 0 };
    }

    for (const roleName of context.subject.roles) {
      const role = this.roles.get(roleName);
      if (!role) continue;

      // Check if role has required permission
      const requiredPermission = `${context.resource.type}:${context.action}`;
      const hasPermission = role.permissions.some(p => 
        p === requiredPermission || 
        p === `${context.resource.type}:*` ||
        p === '*'
      );

      if (hasPermission) {
        // Check role conditions
        if (role.conditions && !this.evaluateConditions(role.conditions, context)) {
          reasons.push(`Role ${roleName} conditions not met`);
          continue;
        }

        allowed = true;
        policies.push(`rbac:role:${roleName}`);
        reasons.push(`Allowed by role: ${roleName}`);
      }
    }

    return {
      matched: policies.length > 0,
      allowed,
      policies,
      reasons,
      priority: 10
    };
  }

  /**
   * Evaluate ABAC policies
   */
  private evaluateABAC(context: PolicyEvaluationContext): {
    matched: boolean;
    allowed: boolean;
    policies: string[];
    reasons: string[];
    priority: number;
  } {
    const policies: string[] = [];
    const reasons: string[] = [];
    let allowed = false;

    // Check subject attributes
    const subjectAttrs = context.subject.attributes || {};
    const resourceAttrs = context.resource.attributes || {};
    const envAttrs = {
      time: context.environment.time,
      ip_address: context.environment.ip_address,
      mfa_verified: context.environment.mfa_verified,
      risk_score: context.environment.risk_score
    };

    // Example ABAC rules (would be configurable in production)
    const abacRules = [
      {
        name: 'owner-access',
        condition: () => resourceAttrs.owner === context.subject.id,
        effect: 'allow',
        reason: 'Resource owner has full access'
      },
      {
        name: 'time-restriction',
        condition: () => {
          const hour = context.environment.time.getHours();
          return hour >= 8 && hour < 18; // Business hours only
        },
        effect: 'allow',
        reason: 'Access allowed during business hours'
      },
      {
        name: 'high-risk-mfa',
        condition: () => {
          const riskScore = context.environment.risk_score || 0;
          return riskScore > 0.5 && !context.environment.mfa_verified;
        },
        effect: 'deny',
        reason: 'High-risk operation requires MFA'
      },
      {
        name: 'department-access',
        condition: () => {
          return subjectAttrs.department === resourceAttrs.department;
        },
        effect: 'allow',
        reason: 'Same department access allowed'
      }
    ];

    for (const rule of abacRules) {
      try {
        if (rule.condition()) {
          policies.push(`abac:${rule.name}`);
          reasons.push(rule.reason);
          if (rule.effect === 'deny') {
            allowed = false;
            break; // Deny takes precedence
          } else {
            allowed = true;
          }
        }
      } catch (error) {
        // Skip rule if evaluation fails
        continue;
      }
    }

    return {
      matched: policies.length > 0,
      allowed,
      policies,
      reasons,
      priority: 20 // ABAC has higher priority than RBAC
    };
  }

  /**
   * Evaluate a single policy document
   */
  private evaluatePolicy(policy: PolicyDocument, context: PolicyEvaluationContext): {
    matched: boolean;
    effect: 'allow' | 'deny';
    reasons: string[];
    obligations?: PolicyObligation[];
    advice?: PolicyAdvice[];
  } {
    const reasons: string[] = [];
    const obligations: PolicyObligation[] = [];
    const advice: PolicyAdvice[] = [];
    let matched = false;
    let effect: 'allow' | 'deny' = 'deny';

    for (const rule of policy.rules) {
      // Check if rule conditions match
      if (rule.conditions && !this.evaluateConditions(rule.conditions, context)) {
        continue;
      }

      // In production, would evaluate Rego rules
      // For now, simple matching logic
      matched = true;
      effect = rule.effect;
      reasons.push(`${rule.name}: ${rule.description || 'No description'}`);

      // Add any obligations
      if (rule.effect === 'allow') {
        obligations.push({
          id: crypto.randomUUID(),
          type: 'audit',
          parameters: { policy: policy.id, rule: rule.name },
          mandatory: true
        });
      }
    }

    return { matched, effect, reasons, obligations, advice };
  }

  /**
   * Evaluate conditions
   */
  private evaluateConditions(conditions: PolicyCondition[], context: PolicyEvaluationContext): boolean {
    for (const condition of conditions) {
      const value = this.getContextValue(condition.field, context);
      
      if (!this.evaluateCondition(condition, value)) {
        return false;
      }
    }
    return true;
  }

  /**
   * Evaluate a single condition
   */
  private evaluateCondition(condition: PolicyCondition, value: any): boolean {
    switch (condition.operator) {
      case 'eq':
        return value === condition.value;
      case 'neq':
        return value !== condition.value;
      case 'gt':
        return value > condition.value;
      case 'gte':
        return value >= condition.value;
      case 'lt':
        return value < condition.value;
      case 'lte':
        return value <= condition.value;
      case 'in':
        return Array.isArray(condition.value) && condition.value.includes(value);
      case 'not_in':
        return Array.isArray(condition.value) && !condition.value.includes(value);
      case 'contains':
        return String(value).includes(String(condition.value));
      case 'matches':
        return new RegExp(String(condition.value)).test(String(value));
      default:
        return false;
    }
  }

  /**
   * Get value from context using dot notation
   */
  private getContextValue(field: string, context: PolicyEvaluationContext): any {
    const parts = field.split('.');
    let value: any = context;

    for (const part of parts) {
      value = value?.[part];
      if (value === undefined) break;
    }

    return value;
  }

  /**
   * Calculate risk score for the operation
   */
  private calculateRiskScore(context: PolicyEvaluationContext, allowed: boolean): number {
    let score = 0;

    // Base risk from environment
    score += context.environment.risk_score || 0;

    // High-risk actions
    const highRiskActions = ['delete', 'modify', 'grant', 'revoke', 'export'];
    if (highRiskActions.includes(context.action)) {
      score += 0.3;
    }

    // Sensitive resources
    const sensitiveResources = ['user', 'role', 'policy', 'payment', 'audit'];
    if (sensitiveResources.includes(context.resource.type)) {
      score += 0.2;
    }

    // Lack of MFA
    if (!context.environment.mfa_verified) {
      score += 0.2;
    }

    // Denied operations are higher risk (potential attack)
    if (!allowed) {
      score += 0.3;
    }

    return Math.min(score, 1.0);
  }

  /**
   * Evaluate with external OPA server
   */
  private async evaluateWithOPA(context: PolicyEvaluationContext): Promise<PolicyEvaluationResult> {
    if (!this.config.opaEndpoint) {
      throw new Error('OPA endpoint not configured');
    }

    const startTime = Date.now();

    try {
      const response = await fetch(`${this.config.opaEndpoint}/v1/data/authz/allow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: context }),
        signal: AbortSignal.timeout(this.config.evaluationTimeout || 5000)
      });

      const result = await response.json();

      return {
        allowed: result.result === true,
        reasons: result.reasons || [],
        matched_policies: result.policies || [],
        evaluation_time_ms: Date.now() - startTime,
        obligations: result.obligations,
        advice: result.advice
      };
    } catch (error) {
      throw new Error(`OPA evaluation failed: ${error}`);
    }
  }

  /**
   * Add or update a policy
   */
  async upsertPolicy(policy: PolicyDocument): Promise<void> {
    const existingPolicy = this.policies.get(policy.id);

    // Version management
    if (this.config.enablePolicyVersioning && existingPolicy) {
      const versions = this.policyVersions.get(policy.id) || [];
      versions.push(existingPolicy);
      
      // Limit version history
      const maxVersions = this.config.maxVersionHistory || 10;
      if (versions.length > maxVersions) {
        versions.shift();
      }
      
      this.policyVersions.set(policy.id, versions);
    }

    // Update policy
    policy.metadata.updated_at = new Date();
    this.policies.set(policy.id, policy);

    // Clear cache when policies change
    this.evaluationCache.clear();

    this.emit('policy:updated', policy);
  }

  /**
   * Remove a policy
   */
  async removePolicy(policyId: string): Promise<void> {
    const policy = this.policies.get(policyId);
    if (!policy) return;

    this.policies.delete(policyId);
    this.evaluationCache.clear();

    this.emit('policy:removed', policy);
  }

  /**
   * Add or update a role
   */
  async upsertRole(role: RBACRole): Promise<void> {
    // Handle role inheritance
    if (role.parent_roles) {
      const inheritedPermissions = new Set(role.permissions);
      
      for (const parentId of role.parent_roles) {
        const parent = this.roles.get(parentId);
        if (parent) {
          parent.permissions.forEach(p => inheritedPermissions.add(p));
        }
      }
      
      role.permissions = Array.from(inheritedPermissions);
    }

    this.roles.set(role.id, role);
    this.evaluationCache.clear();

    this.emit('role:updated', role);
  }

  /**
   * Remove a role
   */
  async removeRole(roleId: string): Promise<void> {
    const role = this.roles.get(roleId);
    if (!role) return;

    // Check for dependent roles
    for (const [id, r] of this.roles) {
      if (r.parent_roles?.includes(roleId)) {
        throw new Error(`Cannot remove role ${roleId}: role ${id} depends on it`);
      }
    }

    this.roles.delete(roleId);
    this.evaluationCache.clear();

    this.emit('role:removed', role);
  }

  /**
   * Register an attribute for ABAC
   */
  async registerAttribute(attribute: ABACAttribute): Promise<void> {
    this.attributes.set(attribute.name, attribute);
    this.emit('attribute:registered', attribute);
  }

  /**
   * Get cache key for evaluation context
   */
  private getCacheKey(context: PolicyEvaluationContext): string {
    return crypto.createHash('sha256').update(JSON.stringify({
      subject_id: context.subject.id,
      resource_type: context.resource.type,
      resource_id: context.resource.id,
      action: context.action
    })).digest('hex');
  }

  /**
   * Check if cache entry is still valid
   */
  private isCacheValid(entry: PolicyEvaluationResult, now: number): boolean {
    const ttl = this.config.cacheTTL || this.CACHE_TTL_MS;
    // Rough estimation - would need to store timestamp in production
    return true; // Simplified for now
  }

  /**
   * Initialize default policies
   */
  private initializeDefaultPolicies(): void {
    // Default admin policy
    const adminPolicy: PolicyDocument = {
      id: 'default-admin',
      version: '1.0.0',
      name: 'Admin Full Access',
      package: 'authz.admin',
      rules: [{
        name: 'admin-all',
        rule: 'allow',
        effect: 'allow',
        conditions: [{
          type: 'attribute',
          operator: 'in',
          field: 'subject.roles',
          value: ['admin', 'super_admin']
        }]
      }],
      metadata: {
        author: 'system',
        created_at: new Date(),
        updated_at: new Date(),
        tags: ['default', 'admin'],
        compliance: ['sox', 'gdpr']
      },
      active: true
    };

    this.policies.set(adminPolicy.id, adminPolicy);
  }

  /**
   * Initialize default roles
   */
  private initializeDefaultRoles(): void {
    const defaultRoles: RBACRole[] = [
      {
        id: 'super_admin',
        name: 'Super Admin',
        permissions: ['*'],
        description: 'Full system access'
      },
      {
        id: 'admin',
        name: 'Admin',
        permissions: [
          'user:*',
          'role:*',
          'policy:read',
          'audit:*',
          'organization:*'
        ],
        parent_roles: [],
        description: 'Administrative access'
      },
      {
        id: 'user',
        name: 'User',
        permissions: [
          'user:read:self',
          'user:update:self',
          'organization:read',
          'session:*:self'
        ],
        description: 'Standard user access'
      },
      {
        id: 'viewer',
        name: 'Viewer',
        permissions: [
          'user:read',
          'organization:read',
          'resource:read'
        ],
        description: 'Read-only access'
      }
    ];

    for (const role of defaultRoles) {
      this.roles.set(role.id, role);
    }
  }

  /**
   * Export policies for backup
   */
  async exportPolicies(): Promise<{
    policies: PolicyDocument[];
    roles: RBACRole[];
    attributes: ABACAttribute[];
  }> {
    return {
      policies: Array.from(this.policies.values()),
      roles: Array.from(this.roles.values()),
      attributes: Array.from(this.attributes.values())
    };
  }

  /**
   * Import policies from backup
   */
  async importPolicies(data: {
    policies: PolicyDocument[];
    roles: RBACRole[];
    attributes: ABACAttribute[];
  }): Promise<void> {
    // Clear existing
    this.policies.clear();
    this.roles.clear();
    this.attributes.clear();
    this.evaluationCache.clear();

    // Import new
    for (const policy of data.policies) {
      this.policies.set(policy.id, policy);
    }
    for (const role of data.roles) {
      this.roles.set(role.id, role);
    }
    for (const attr of data.attributes) {
      this.attributes.set(attr.name, attr);
    }

    this.emit('policies:imported', {
      policies: data.policies.length,
      roles: data.roles.length,
      attributes: data.attributes.length
    });
  }

  /**
   * Get policy statistics
   */
  getStatistics(): {
    total_policies: number;
    active_policies: number;
    total_roles: number;
    total_attributes: number;
    cache_size: number;
  } {
    const activePolicies = Array.from(this.policies.values()).filter(p => p.active).length;

    return {
      total_policies: this.policies.size,
      active_policies: activePolicies,
      total_roles: this.roles.size,
      total_attributes: this.attributes.size,
      cache_size: this.evaluationCache.size
    };
  }
}