# Enterprise Admin Portal & Dashboard

## Overview

The Plinto Admin Portal provides comprehensive organization management, user administration, security monitoring, and analytics capabilities through an intuitive web-based interface designed for enterprise administrators and security teams.

## Portal Architecture

### Component Structure

```typescript
// Admin Portal Architecture
interface AdminPortal {
  // Core Modules
  modules: {
    dashboard: DashboardModule;
    users: UserManagementModule;
    security: SecurityModule;
    analytics: AnalyticsModule;
    audit: AuditModule;
    settings: SettingsModule;
    billing: BillingModule;
    support: SupportModule;
  };
  
  // Access Control
  rbac: {
    roles: AdminRole[];
    permissions: Permission[];
    policies: AccessPolicy[];
  };
  
  // Customization
  branding: BrandingConfig;
  whiteLabel: WhiteLabelConfig;
  customModules: CustomModule[];
}

// Role-Based Access Control
interface AdminRole {
  id: string;
  name: string;
  permissions: string[];
  
  // Hierarchy
  parent?: string;
  children?: string[];
  
  // Constraints
  maxUsers?: number;
  expiresAt?: Date;
  
  // Custom permissions
  customPermissions?: {
    resource: string;
    actions: string[];
    conditions?: PolicyCondition[];
  }[];
}
```

## Dashboard Module

### Executive Dashboard

```tsx
// Dashboard Component Implementation
import { Dashboard, Widget, Chart } from '@plinto/admin-ui';

export function ExecutiveDashboard() {
  return (
    <Dashboard layout="executive">
      {/* Key Metrics */}
      <Widget.MetricGrid>
        <Widget.Metric
          title="Active Users"
          value={12543}
          change={+15.2}
          period="30d"
          icon="users"
        />
        <Widget.Metric
          title="Security Score"
          value={94}
          change={+2}
          period="7d"
          icon="shield"
          severity={getScoreSeverity(94)}
        />
        <Widget.Metric
          title="API Calls"
          value="2.3M"
          change={+8.7}
          period="24h"
          icon="activity"
        />
        <Widget.Metric
          title="Compliance Rate"
          value="99.8%"
          change={0}
          period="30d"
          icon="check-circle"
        />
      </Widget.MetricGrid>
      
      {/* Activity Timeline */}
      <Widget.Timeline
        title="Recent Activity"
        events={recentEvents}
        filters={['security', 'users', 'system']}
      />
      
      {/* Security Overview */}
      <Widget.Security>
        <Chart.ThreatMap
          data={threatData}
          realtime={true}
          resolution="country"
        />
        <Chart.RiskMatrix
          risks={currentRisks}
          interactive={true}
        />
      </Widget.Security>
      
      {/* Usage Analytics */}
      <Widget.Analytics>
        <Chart.LineGraph
          title="Authentication Trends"
          data={authTrends}
          lines={['successful', 'failed', 'mfa']}
          period="30d"
        />
        <Chart.PieChart
          title="Auth Methods"
          data={authMethods}
          showLegend={true}
        />
      </Widget.Analytics>
    </Dashboard>
  );
}
```

### Real-time Monitoring

```typescript
class RealtimeMonitor {
  private websocket: WebSocket;
  private subscribers: Map<string, Subscriber[]> = new Map();
  
  async connect() {
    this.websocket = new WebSocket('wss://api.plinto.dev/admin/realtime');
    
    this.websocket.on('message', (data) => {
      const event = JSON.parse(data);
      this.handleRealtimeEvent(event);
    });
    
    // Subscribe to channels
    await this.subscribe([
      'security.threats',
      'auth.failures',
      'system.alerts',
      'user.activity',
      'api.errors'
    ]);
  }
  
  private handleRealtimeEvent(event: RealtimeEvent) {
    switch (event.type) {
      case 'THREAT_DETECTED':
        this.notifyThreat(event);
        break;
        
      case 'BRUTE_FORCE_ATTEMPT':
        this.handleBruteForce(event);
        break;
        
      case 'ANOMALY_DETECTED':
        this.handleAnomaly(event);
        break;
        
      case 'SYSTEM_ALERT':
        this.handleSystemAlert(event);
        break;
    }
    
    // Notify subscribers
    this.notifySubscribers(event);
  }
  
  async getRealtimeMetrics(): Promise<RealtimeMetrics> {
    return {
      activeUsers: await this.getActiveUserCount(),
      apiCallsPerSecond: await this.getAPICallRate(),
      authSuccessRate: await this.getAuthSuccessRate(),
      avgResponseTime: await this.getAvgResponseTime(),
      errorRate: await this.getErrorRate(),
      
      // Security metrics
      threatLevel: await this.getCurrentThreatLevel(),
      activeThreats: await this.getActiveThreats(),
      blockedAttempts: await this.getBlockedAttempts()
    };
  }
}
```

## User Management Module

### User Administration Interface

```tsx
// User Management Component
export function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [filters, setFilters] = useState<UserFilters>({});
  
  return (
    <Module title="User Management">
      {/* Search and Filters */}
      <SearchBar
        placeholder="Search users by name, email, or ID"
        onSearch={handleSearch}
        filters={
          <FilterPanel>
            <Filter.Select
              label="Status"
              options={['Active', 'Inactive', 'Suspended', 'Pending']}
            />
            <Filter.Select
              label="Role"
              options={roles}
            />
            <Filter.DateRange
              label="Created"
            />
            <Filter.Tags
              label="Groups"
              options={groups}
            />
          </FilterPanel>
        }
      />
      
      {/* User Table */}
      <DataTable
        data={users}
        columns={[
          { key: 'avatar', render: (user) => <Avatar user={user} /> },
          { key: 'name', sortable: true },
          { key: 'email', sortable: true },
          { key: 'role', render: (user) => <RoleBadge role={user.role} /> },
          { key: 'status', render: (user) => <StatusIndicator status={user.status} /> },
          { key: 'lastActive', sortable: true, render: formatDateTime },
          { key: 'mfaEnabled', render: (user) => <MFAStatus enabled={user.mfaEnabled} /> },
          {
            key: 'actions',
            render: (user) => (
              <ActionMenu>
                <Action onClick={() => editUser(user)}>Edit</Action>
                <Action onClick={() => resetPassword(user)}>Reset Password</Action>
                <Action onClick={() => suspend(user)} danger>Suspend</Action>
              </ActionMenu>
            )
          }
        ]}
        pagination={true}
        selection="multiple"
        bulkActions={
          <BulkActions>
            <Action>Export Selected</Action>
            <Action>Assign Role</Action>
            <Action>Add to Group</Action>
            <Action danger>Suspend Selected</Action>
          </BulkActions>
        }
      />
    </Module>
  );
}
```

### Bulk User Operations

```typescript
class BulkUserOperations {
  async importUsers(file: File, options: ImportOptions): Promise<ImportResult> {
    const users = await this.parseUserFile(file);
    
    // Validate users
    const validation = await this.validateUsers(users);
    if (validation.errors.length > 0) {
      return {
        success: false,
        errors: validation.errors
      };
    }
    
    // Process in batches
    const batchSize = 100;
    const results = [];
    
    for (let i = 0; i < users.length; i += batchSize) {
      const batch = users.slice(i, i + batchSize);
      
      const batchResult = await this.processBatch(batch, {
        ...options,
        
        // Progress callback
        onProgress: (progress) => {
          this.updateProgress({
            processed: i + progress.processed,
            total: users.length,
            errors: progress.errors
          });
        }
      });
      
      results.push(batchResult);
    }
    
    return {
      success: true,
      imported: results.reduce((acc, r) => acc + r.imported, 0),
      failed: results.reduce((acc, r) => acc + r.failed, 0),
      errors: results.flatMap(r => r.errors)
    };
  }
  
  async exportUsers(filters: UserFilters, format: ExportFormat): Promise<Blob> {
    const users = await this.fetchUsers(filters);
    
    switch (format) {
      case 'csv':
        return this.exportAsCSV(users);
      case 'json':
        return this.exportAsJSON(users);
      case 'xlsx':
        return this.exportAsExcel(users);
      case 'pdf':
        return this.exportAsPDF(users);
    }
  }
  
  async bulkUpdate(userIds: string[], updates: UserUpdates): Promise<BulkUpdateResult> {
    // Validate permissions
    await this.validateBulkPermissions(userIds, updates);
    
    // Create audit log
    const auditId = await this.audit.startBulkOperation({
      type: 'USER_BULK_UPDATE',
      affectedUsers: userIds.length,
      changes: updates
    });
    
    try {
      const results = await Promise.allSettled(
        userIds.map(id => this.updateUser(id, updates))
      );
      
      const successful = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected');
      
      await this.audit.completeBulkOperation(auditId, {
        successful,
        failed: failed.length,
        errors: failed.map(f => f.reason)
      });
      
      return {
        successful,
        failed: failed.length,
        errors: failed.map(f => ({
          userId: f.userId,
          error: f.reason
        }))
      };
    } catch (error) {
      await this.audit.failBulkOperation(auditId, error);
      throw error;
    }
  }
}
```

## Security Module

### Security Dashboard

```tsx
export function SecurityDashboard() {
  return (
    <SecurityModule>
      {/* Threat Overview */}
      <ThreatOverview>
        <ThreatIndicator level={threatLevel} />
        <ActiveThreats threats={activeThreats} />
        <BlockedAttempts count={blockedCount} trend={trend} />
      </ThreatOverview>
      
      {/* Security Events */}
      <EventStream
        events={securityEvents}
        filters={['critical', 'high', 'medium']}
        realtime={true}
      />
      
      {/* Risk Assessment */}
      <RiskMatrix
        risks={identifiedRisks}
        interactive={true}
        onRiskClick={handleRiskDetails}
      />
      
      {/* Policy Violations */}
      <PolicyViolations
        violations={violations}
        groupBy="policy"
        timeRange="24h"
      />
      
      {/* Security Controls */}
      <SecurityControls>
        <Control
          name="MFA Enforcement"
          status="enabled"
          coverage="87%"
          onToggle={toggleMFA}
        />
        <Control
          name="IP Restrictions"
          status="partial"
          coverage="45%"
          onConfigure={configureIPRules}
        />
        <Control
          name="Session Monitoring"
          status="enabled"
          coverage="100%"
        />
      </SecurityControls>
    </SecurityModule>
  );
}
```

### Threat Intelligence Integration

```typescript
class ThreatIntelligenceService {
  private feeds: ThreatFeed[] = [];
  
  async initializeFeeds() {
    this.feeds = [
      new IPReputationFeed(),
      new MalwareFeed(),
      new PhishingFeed(),
      new CVEFeed(),
      new ThreatActorFeed()
    ];
    
    // Start feed synchronization
    for (const feed of this.feeds) {
      await feed.sync();
      
      // Set up continuous updates
      feed.onUpdate((data) => this.processThreatData(data));
    }
  }
  
  async analyzeEntity(entity: Entity): Promise<ThreatAnalysis> {
    const results = await Promise.all(
      this.feeds.map(feed => feed.analyze(entity))
    );
    
    return {
      entity,
      threats: results.filter(r => r.threatDetected),
      riskScore: this.calculateRiskScore(results),
      recommendations: this.generateRecommendations(results),
      
      // Detailed analysis
      ipReputation: results.find(r => r.type === 'ip_reputation'),
      malwareAssociation: results.find(r => r.type === 'malware'),
      knownAttacker: results.find(r => r.type === 'threat_actor')
    };
  }
  
  async generateThreatReport(organizationId: string): Promise<ThreatReport> {
    const period = { start: subDays(new Date(), 30), end: new Date() };
    
    const [
      threats,
      incidents,
      vulnerabilities,
      indicators
    ] = await Promise.all([
      this.getDetectedThreats(organizationId, period),
      this.getSecurityIncidents(organizationId, period),
      this.getVulnerabilities(organizationId),
      this.getCompromiseIndicators(organizationId)
    ]);
    
    return {
      executive_summary: this.generateExecutiveSummary(threats, incidents),
      
      threat_landscape: {
        active_threats: threats.filter(t => t.status === 'active'),
        mitigated_threats: threats.filter(t => t.status === 'mitigated'),
        threat_trends: this.analyzeThreatTrends(threats)
      },
      
      incidents: {
        total: incidents.length,
        by_severity: this.groupBySeverity(incidents),
        mean_time_to_detect: this.calculateMTTD(incidents),
        mean_time_to_respond: this.calculateMTTR(incidents)
      },
      
      vulnerabilities: {
        critical: vulnerabilities.filter(v => v.severity === 'critical'),
        high: vulnerabilities.filter(v => v.severity === 'high'),
        patched: vulnerabilities.filter(v => v.patched),
        pending: vulnerabilities.filter(v => !v.patched)
      },
      
      recommendations: this.generateSecurityRecommendations(threats, incidents, vulnerabilities)
    };
  }
}
```

## Analytics Module

### Advanced Analytics Dashboard

```typescript
class AnalyticsEngine {
  async generateAnalytics(params: AnalyticsParams): Promise<AnalyticsData> {
    const [
      usage,
      performance,
      security,
      compliance,
      costs
    ] = await Promise.all([
      this.getUsageAnalytics(params),
      this.getPerformanceAnalytics(params),
      this.getSecurityAnalytics(params),
      this.getComplianceAnalytics(params),
      this.getCostAnalytics(params)
    ]);
    
    return {
      period: params.period,
      
      // Usage Analytics
      usage: {
        activeUsers: usage.dau,
        apiCalls: usage.apiCalls,
        authentication: {
          total: usage.auth.total,
          byMethod: usage.auth.methods,
          mfaAdoption: usage.auth.mfaRate,
          passwordless: usage.auth.passwordlessRate
        },
        
        // Feature adoption
        featureAdoption: {
          sso: usage.features.sso,
          webhooks: usage.features.webhooks,
          policies: usage.features.policies
        }
      },
      
      // Performance Analytics
      performance: {
        availability: performance.uptime,
        responseTime: {
          p50: performance.latency.p50,
          p95: performance.latency.p95,
          p99: performance.latency.p99
        },
        errorRate: performance.errors,
        
        // API performance
        apiPerformance: performance.endpoints.map(e => ({
          endpoint: e.path,
          calls: e.calls,
          avgTime: e.avgLatency,
          errors: e.errorRate
        }))
      },
      
      // Security Analytics
      security: {
        securityScore: security.score,
        threats: {
          detected: security.threats.total,
          blocked: security.threats.blocked,
          byType: security.threats.types
        },
        
        incidents: security.incidents,
        vulnerabilities: security.vulnerabilities
      },
      
      // Predictive Analytics
      predictions: await this.generatePredictions(usage, performance)
    };
  }
  
  async generatePredictions(usage: UsageData, performance: PerformanceData): Promise<Predictions> {
    // ML-based predictions
    const model = await this.loadPredictionModel();
    
    return {
      // Growth predictions
      userGrowth: model.predictUserGrowth(usage),
      apiUsage: model.predictAPIUsage(usage),
      
      // Capacity planning
      capacityNeeds: model.predictCapacity(usage, performance),
      
      // Security predictions
      threatProbability: model.predictThreats(this.historicalThreats),
      
      // Cost projections
      costProjection: model.predictCosts(usage, this.pricingModel)
    };
  }
}
```

### Custom Reports Builder

```tsx
export function ReportBuilder() {
  const [report, setReport] = useState<CustomReport>({
    name: '',
    widgets: [],
    schedule: null
  });
  
  return (
    <ReportBuilderModule>
      {/* Report Configuration */}
      <ReportConfig>
        <Input
          label="Report Name"
          value={report.name}
          onChange={(name) => setReport({...report, name})}
        />
        
        <Select
          label="Schedule"
          options={['Daily', 'Weekly', 'Monthly', 'Quarterly']}
          onChange={(schedule) => setReport({...report, schedule})}
        />
        
        <MultiSelect
          label="Recipients"
          options={users}
          onChange={(recipients) => setReport({...report, recipients})}
        />
      </ReportConfig>
      
      {/* Widget Selection */}
      <WidgetGallery>
        <WidgetCategory title="Metrics">
          <DraggableWidget type="metric" config={metricConfig} />
          <DraggableWidget type="kpi" config={kpiConfig} />
        </WidgetCategory>
        
        <WidgetCategory title="Charts">
          <DraggableWidget type="line" config={lineConfig} />
          <DraggableWidget type="bar" config={barConfig} />
          <DraggableWidget type="pie" config={pieConfig} />
        </WidgetCategory>
        
        <WidgetCategory title="Tables">
          <DraggableWidget type="datatable" config={tableConfig} />
          <DraggableWidget type="pivot" config={pivotConfig} />
        </WidgetCategory>
      </WidgetGallery>
      
      {/* Report Canvas */}
      <ReportCanvas
        widgets={report.widgets}
        onDrop={handleWidgetDrop}
        onResize={handleWidgetResize}
        onRemove={handleWidgetRemove}
        onConfigure={handleWidgetConfig}
      />
      
      {/* Preview and Actions */}
      <ReportActions>
        <Button onClick={previewReport}>Preview</Button>
        <Button onClick={saveReport} primary>Save Report</Button>
        <Button onClick={scheduleReport}>Schedule</Button>
        <Button onClick={exportReport}>Export</Button>
      </ReportActions>
    </ReportBuilderModule>
  );
}
```

## Audit Module

### Comprehensive Audit Logging

```typescript
class AuditLogger {
  async logAdminAction(action: AdminAction) {
    const entry: AuditEntry = {
      id: generateId(),
      timestamp: new Date(),
      
      // Actor information
      actor: {
        id: action.userId,
        email: action.userEmail,
        role: action.userRole,
        ipAddress: action.ipAddress,
        userAgent: action.userAgent
      },
      
      // Action details
      action: {
        type: action.type,
        resource: action.resource,
        operation: action.operation,
        
        // Change tracking
        before: action.previousState,
        after: action.newState,
        diff: this.calculateDiff(action.previousState, action.newState)
      },
      
      // Context
      context: {
        sessionId: action.sessionId,
        organizationId: action.organizationId,
        correlationId: action.correlationId,
        
        // Additional metadata
        tags: action.tags,
        notes: action.notes
      },
      
      // Compliance
      compliance: {
        regulations: this.getApplicableRegulations(action),
        dataClassification: this.classifyData(action),
        retentionPeriod: this.getRetentionPeriod(action)
      }
    };
    
    // Store in multiple locations for redundancy
    await Promise.all([
      this.storeInDatabase(entry),
      this.storeInTimeSeries(entry),
      this.storeInColdStorage(entry),
      this.forwardToSIEM(entry)
    ]);
    
    // Real-time alerting
    if (this.requiresAlert(action)) {
      await this.sendAlert(entry);
    }
    
    return entry;
  }
  
  async searchAuditLogs(query: AuditQuery): Promise<AuditSearchResult> {
    // Build search query
    const esQuery = this.buildElasticsearchQuery(query);
    
    // Execute search
    const results = await this.elasticsearch.search({
      index: 'audit-logs',
      body: esQuery
    });
    
    // Format results
    return {
      total: results.hits.total.value,
      entries: results.hits.hits.map(hit => this.formatAuditEntry(hit._source)),
      
      // Aggregations
      aggregations: {
        byUser: results.aggregations?.users,
        byAction: results.aggregations?.actions,
        byResource: results.aggregations?.resources,
        timeline: results.aggregations?.timeline
      },
      
      // Export options
      exportFormats: ['csv', 'json', 'pdf'],
      exportUrl: this.generateExportUrl(query)
    };
  }
}
```

## Settings Module

### Organization Configuration

```tsx
export function OrganizationSettings() {
  return (
    <SettingsModule>
      {/* General Settings */}
      <SettingsSection title="General">
        <Setting
          label="Organization Name"
          type="text"
          value={org.name}
          onChange={updateOrgName}
        />
        
        <Setting
          label="Primary Domain"
          type="domain"
          value={org.domain}
          onChange={updateDomain}
          validation={validateDomain}
        />
        
        <Setting
          label="Time Zone"
          type="select"
          options={timezones}
          value={org.timezone}
          onChange={updateTimezone}
        />
      </SettingsSection>
      
      {/* Security Settings */}
      <SettingsSection title="Security">
        <Setting
          label="Password Policy"
          type="custom"
          component={<PasswordPolicyEditor policy={passwordPolicy} />}
        />
        
        <Setting
          label="MFA Requirements"
          type="toggle"
          value={security.mfaRequired}
          onChange={toggleMFA}
        />
        
        <Setting
          label="Session Timeout"
          type="duration"
          value={security.sessionTimeout}
          onChange={updateSessionTimeout}
        />
        
        <Setting
          label="IP Whitelist"
          type="iplist"
          value={security.allowedIPs}
          onChange={updateIPWhitelist}
        />
      </SettingsSection>
      
      {/* Branding Settings */}
      <SettingsSection title="Branding">
        <Setting
          label="Logo"
          type="image"
          value={branding.logo}
          onChange={updateLogo}
        />
        
        <Setting
          label="Primary Color"
          type="color"
          value={branding.primaryColor}
          onChange={updatePrimaryColor}
        />
        
        <Setting
          label="Custom CSS"
          type="code"
          language="css"
          value={branding.customCSS}
          onChange={updateCustomCSS}
        />
      </SettingsSection>
    </SettingsModule>
  );
}
```

## API Access

### Admin API Integration

```typescript
// Admin API Client
class PlintoAdminAPI {
  constructor(config: AdminAPIConfig) {
    this.client = new APIClient({
      baseUrl: 'https://api.plinto.dev/admin/v1',
      apiKey: config.apiKey,
      
      // Admin-specific headers
      headers: {
        'X-Admin-Token': config.adminToken,
        'X-Organization-Id': config.organizationId
      }
    });
  }
  
  // User Management
  users = {
    list: (params?: UserListParams) => this.client.get('/users', params),
    get: (id: string) => this.client.get(`/users/${id}`),
    create: (user: UserCreate) => this.client.post('/users', user),
    update: (id: string, updates: UserUpdate) => this.client.patch(`/users/${id}`, updates),
    delete: (id: string) => this.client.delete(`/users/${id}`),
    
    // Bulk operations
    bulkCreate: (users: UserCreate[]) => this.client.post('/users/bulk', { users }),
    bulkUpdate: (updates: BulkUserUpdate) => this.client.patch('/users/bulk', updates),
    bulkDelete: (ids: string[]) => this.client.delete('/users/bulk', { ids })
  };
  
  // Security Management
  security = {
    threats: () => this.client.get('/security/threats'),
    incidents: (params?: IncidentParams) => this.client.get('/security/incidents', params),
    policies: () => this.client.get('/security/policies'),
    
    // Actions
    blockIP: (ip: string) => this.client.post('/security/block-ip', { ip }),
    unblockIP: (ip: string) => this.client.delete(`/security/block-ip/${ip}`),
    enforcePolicy: (policy: SecurityPolicy) => this.client.post('/security/policies', policy)
  };
  
  // Analytics
  analytics = {
    dashboard: (period: DateRange) => this.client.get('/analytics/dashboard', { period }),
    usage: (params: UsageParams) => this.client.get('/analytics/usage', params),
    performance: (params: PerformanceParams) => this.client.get('/analytics/performance', params),
    
    // Custom queries
    query: (query: AnalyticsQuery) => this.client.post('/analytics/query', query),
    
    // Reports
    generateReport: (config: ReportConfig) => this.client.post('/analytics/reports', config),
    scheduleReport: (schedule: ReportSchedule) => this.client.post('/analytics/reports/schedule', schedule)
  };
  
  // Audit Logs
  audit = {
    search: (query: AuditQuery) => this.client.post('/audit/search', query),
    export: (params: ExportParams) => this.client.post('/audit/export', params),
    stream: (callback: (event: AuditEvent) => void) => {
      const ws = new WebSocket('wss://api.plinto.dev/admin/v1/audit/stream');
      ws.on('message', (data) => callback(JSON.parse(data)));
      return ws;
    }
  };
}
```

## Mobile Admin App

### React Native Implementation

```tsx
// Mobile Admin Dashboard
import { AdminMobile } from '@plinto/admin-mobile';

export function MobileAdminApp() {
  return (
    <AdminMobile>
      {/* Quick Actions */}
      <QuickActions>
        <Action icon="user-check" onPress={approveUsers}>
          Approve Users
        </Action>
        <Action icon="shield" onPress={viewThreats}>
          Security Alerts
        </Action>
        <Action icon="activity" onPress={viewMetrics}>
          Live Metrics
        </Action>
      </QuickActions>
      
      {/* Notifications */}
      <NotificationCenter
        notifications={notifications}
        onNotificationPress={handleNotification}
      />
      
      {/* Mobile-Optimized Modules */}
      <TabNavigator>
        <Tab name="Dashboard" component={MobileDashboard} />
        <Tab name="Users" component={MobileUserList} />
        <Tab name="Security" component={MobileSecurityView} />
        <Tab name="Alerts" component={MobileAlerts} />
      </TabNavigator>
    </AdminMobile>
  );
}
```

## Customization & White-Label

### White-Label Configuration

```typescript
interface WhiteLabelConfig {
  // Branding
  branding: {
    companyName: string;
    logo: {
      light: string;
      dark: string;
      favicon: string;
    };
    colors: {
      primary: string;
      secondary: string;
      accent: string;
      error: string;
      warning: string;
      success: string;
    };
    fonts: {
      heading: string;
      body: string;
      mono: string;
    };
  };
  
  // Custom Domain
  domain: {
    admin: string; // admin.company.com
    api: string;   // api.company.com
    cdn: string;   // cdn.company.com
  };
  
  // Feature Toggles
  features: {
    sso: boolean;
    mfa: boolean;
    webhooks: boolean;
    policies: boolean;
    customModules: boolean;
  };
  
  // Custom Modules
  modules?: CustomModule[];
  
  // Email Templates
  emailTemplates?: {
    welcome?: string;
    passwordReset?: string;
    mfaSetup?: string;
  };
}

// Apply white-label configuration
async function applyWhiteLabel(config: WhiteLabelConfig) {
  // Update branding
  await updateBranding(config.branding);
  
  // Configure custom domain
  await configureDomain(config.domain);
  
  // Apply feature toggles
  await applyFeatureFlags(config.features);
  
  // Register custom modules
  if (config.modules) {
    await registerModules(config.modules);
  }
  
  // Update email templates
  if (config.emailTemplates) {
    await updateEmailTemplates(config.emailTemplates);
  }
}
```

## Support & Documentation

- Admin Portal Guide: https://docs.plinto.dev/admin-portal
- API Reference: https://api.plinto.dev/admin/docs
- Video Tutorials: https://plinto.dev/tutorials/admin
- Enterprise Support: enterprise@plinto.dev