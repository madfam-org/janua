import { EventEmitter } from 'events';
import crypto from 'crypto';

export interface AuditLogEntry {
  id: string;
  timestamp: Date;
  actor: {
    id: string;
    type: 'user' | 'system' | 'api_key' | 'service_account';
    email?: string;
    ip_address?: string;
    user_agent?: string;
  };
  action: string;
  resource: {
    type: string;
    id?: string;
    name?: string;
  };
  details: Record<string, any>;
  outcome: 'success' | 'failure' | 'error';
  risk_score?: number;
  compliance_flags?: string[];
  metadata?: {
    session_id?: string;
    correlation_id?: string;
    request_id?: string;
    tenant_id?: string;
    organization_id?: string;
  };
}

export interface AuditQueryOptions {
  actor_id?: string;
  action?: string;
  resource_type?: string;
  resource_id?: string;
  start_date?: Date;
  end_date?: Date;
  outcome?: 'success' | 'failure' | 'error';
  risk_score_min?: number;
  compliance_flag?: string;
  limit?: number;
  offset?: number;
  order?: 'asc' | 'desc';
}

export interface AuditRetentionPolicy {
  retention_days: number;
  archive_enabled: boolean;
  archive_location?: string;
  compliance_mode: 'standard' | 'sox' | 'gdpr' | 'hipaa';
  immutable: boolean;
}

export interface ComplianceReport {
  report_id: string;
  period: {
    start: Date;
    end: Date;
  };
  compliance_standards: string[];
  total_events: number;
  high_risk_events: number;
  failed_actions: number;
  unique_actors: number;
  top_actions: Array<{
    action: string;
    count: number;
  }>;
  anomalies: Array<{
    timestamp: Date;
    description: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
  }>;
}

export class AuditService extends EventEmitter {
  private storage: Map<string, AuditLogEntry> = new Map();
  private retentionPolicy: AuditRetentionPolicy;
  private encryptionKey?: Buffer;
  private readonly MAX_BATCH_SIZE = 1000;
  private batchQueue: AuditLogEntry[] = [];
  private flushTimer?: NodeJS.Timeout;

  constructor(
    private readonly config: {
      encryption?: boolean;
      encryptionKey?: string;
      retentionPolicy?: Partial<AuditRetentionPolicy>;
      batchInterval?: number; // ms
      storageBackend?: 'memory' | 'postgres' | 's3' | 'elasticsearch';
    } = {}
  ) {
    super();
    
    this.retentionPolicy = {
      retention_days: 2555, // 7 years default for SOX compliance
      archive_enabled: true,
      compliance_mode: 'standard',
      immutable: true,
      ...config.retentionPolicy
    };

    if (config.encryption && config.encryptionKey) {
      this.encryptionKey = Buffer.from(config.encryptionKey, 'base64');
    }

    // Start batch processing
    if (config.batchInterval) {
      this.startBatchProcessor(config.batchInterval);
    }

    // Start retention cleanup
    this.startRetentionCleanup();
  }

  /**
   * Log an audit event
   */
  async log(entry: Omit<AuditLogEntry, 'id' | 'timestamp'>): Promise<AuditLogEntry> {
    const logEntry: AuditLogEntry = {
      id: crypto.randomUUID(),
      timestamp: new Date(),
      ...entry
    };

    // Calculate risk score if not provided
    if (!logEntry.risk_score) {
      logEntry.risk_score = this.calculateRiskScore(logEntry);
    }

    // Add compliance flags
    logEntry.compliance_flags = this.determineComplianceFlags(logEntry);

    // Validate immutability
    if (this.retentionPolicy.immutable) {
      logEntry.details._checksum = this.calculateChecksum(logEntry);
    }

    // Add to batch queue
    this.batchQueue.push(logEntry);
    
    // Flush if batch is full
    if (this.batchQueue.length >= this.MAX_BATCH_SIZE) {
      await this.flushBatch();
    }

    // Emit event for real-time monitoring
    this.emit('audit:logged', logEntry);

    // Check for anomalies
    if (logEntry.risk_score > 0.7) {
      this.emit('audit:high-risk', logEntry);
    }

    return logEntry;
  }

  /**
   * Query audit logs
   */
  async query(options: AuditQueryOptions = {}): Promise<{
    entries: AuditLogEntry[];
    total: number;
    has_more: boolean;
  }> {
    let results = Array.from(this.storage.values());

    // Apply filters
    if (options.actor_id) {
      results = results.filter(e => e.actor.id === options.actor_id);
    }
    if (options.action) {
      results = results.filter(e => e.action === options.action);
    }
    if (options.resource_type) {
      results = results.filter(e => e.resource.type === options.resource_type);
    }
    if (options.resource_id) {
      results = results.filter(e => e.resource.id === options.resource_id);
    }
    if (options.outcome) {
      results = results.filter(e => e.outcome === options.outcome);
    }
    if (options.risk_score_min !== undefined) {
      results = results.filter(e => (e.risk_score || 0) >= options.risk_score_min!);
    }
    if (options.compliance_flag) {
      results = results.filter(e => 
        e.compliance_flags?.includes(options.compliance_flag!)
      );
    }

    // Apply date range
    if (options.start_date) {
      results = results.filter(e => e.timestamp >= options.start_date!);
    }
    if (options.end_date) {
      results = results.filter(e => e.timestamp <= options.end_date!);
    }

    // Sort
    results.sort((a, b) => {
      const diff = a.timestamp.getTime() - b.timestamp.getTime();
      return options.order === 'desc' ? -diff : diff;
    });

    // Paginate
    const total = results.length;
    const offset = options.offset || 0;
    const limit = options.limit || 100;
    const entries = results.slice(offset, offset + limit);

    return {
      entries,
      total,
      has_more: offset + limit < total
    };
  }

  /**
   * Generate compliance report
   */
  async generateComplianceReport(
    start: Date,
    end: Date,
    standards: string[] = ['sox', 'gdpr']
  ): Promise<ComplianceReport> {
    const { entries } = await this.query({
      start_date: start,
      end_date: end,
      limit: Number.MAX_SAFE_INTEGER
    });

    // Analyze events
    const actionCounts = new Map<string, number>();
    const actors = new Set<string>();
    let highRiskCount = 0;
    let failedCount = 0;
    const anomalies: ComplianceReport['anomalies'] = [];

    for (const entry of entries) {
      actors.add(entry.actor.id);
      
      // Count actions
      const count = actionCounts.get(entry.action) || 0;
      actionCounts.set(entry.action, count + 1);
      
      // Count high risk
      if ((entry.risk_score || 0) > 0.7) {
        highRiskCount++;
      }
      
      // Count failures
      if (entry.outcome === 'failure' || entry.outcome === 'error') {
        failedCount++;
      }

      // Detect anomalies
      if (this.isAnomaly(entry, entries)) {
        anomalies.push({
          timestamp: entry.timestamp,
          description: `Unusual ${entry.action} by ${entry.actor.type}`,
          severity: this.getAnomalySeverity(entry)
        });
      }
    }

    // Get top actions
    const topActions = Array.from(actionCounts.entries())
      .sort(([, a], [, b]) => b - a)
      .slice(0, 10)
      .map(([action, count]) => ({ action, count }));

    return {
      report_id: crypto.randomUUID(),
      period: { start, end },
      compliance_standards: standards,
      total_events: entries.length,
      high_risk_events: highRiskCount,
      failed_actions: failedCount,
      unique_actors: actors.size,
      top_actions: topActions,
      anomalies: anomalies.slice(0, 100) // Limit anomalies
    };
  }

  /**
   * Export audit logs for archival
   */
  async exportLogs(
    format: 'json' | 'csv' | 'parquet',
    options: AuditQueryOptions = {}
  ): Promise<Buffer> {
    const { entries } = await this.query(options);
    
    switch (format) {
      case 'json':
        return Buffer.from(JSON.stringify(entries, null, 2));
      
      case 'csv':
        return this.exportToCsv(entries);
      
      case 'parquet':
        // Would integrate with a parquet library
        throw new Error('Parquet export not yet implemented');
      
      default:
        throw new Error(`Unsupported export format: ${format}`);
    }
  }

  /**
   * Verify log integrity
   */
  async verifyIntegrity(entryId: string): Promise<boolean> {
    const entry = this.storage.get(entryId);
    if (!entry) return false;

    if (!this.retentionPolicy.immutable) return true;

    const storedChecksum = entry.details._checksum;
    if (!storedChecksum) return false;

    // Temporarily remove checksum for calculation
    const { _checksum, ...details } = entry.details;
    const entryToCheck = { ...entry, details };
    
    const calculatedChecksum = this.calculateChecksum(entryToCheck);
    return storedChecksum === calculatedChecksum;
  }

  /**
   * Calculate risk score for an audit entry
   */
  private calculateRiskScore(entry: Omit<AuditLogEntry, 'id' | 'timestamp'>): number {
    let score = 0;

    // High-risk actions
    const highRiskActions = [
      'user.deleted',
      'role.changed',
      'permission.granted',
      'mfa.disabled',
      'api_key.created',
      'policy.modified',
      'audit.exported',
      'compliance.bypassed'
    ];

    if (highRiskActions.includes(entry.action)) {
      score += 0.5;
    }

    // Failed actions indicate potential attacks
    if (entry.outcome === 'failure') {
      score += 0.2;
    }

    // System actors are lower risk
    if (entry.actor.type === 'system') {
      score *= 0.5;
    }

    // Unusual IP or user agent
    if (entry.actor.ip_address && this.isUnusualIP(entry.actor.ip_address)) {
      score += 0.3;
    }

    // Sensitive resources
    const sensitiveResources = ['user', 'role', 'permission', 'payment', 'audit'];
    if (sensitiveResources.includes(entry.resource.type)) {
      score += 0.2;
    }

    return Math.min(score, 1.0);
  }

  /**
   * Determine compliance flags for an entry
   */
  private determineComplianceFlags(entry: AuditLogEntry): string[] {
    const flags: string[] = [];

    // SOX compliance
    if (['financial', 'payment', 'audit'].includes(entry.resource.type)) {
      flags.push('sox');
    }

    // GDPR compliance
    if (['user', 'personal_data'].includes(entry.resource.type)) {
      flags.push('gdpr');
    }

    // HIPAA compliance
    if (['health_data', 'patient'].includes(entry.resource.type)) {
      flags.push('hipaa');
    }

    // PCI DSS compliance
    if (['payment', 'card_data'].includes(entry.resource.type)) {
      flags.push('pci_dss');
    }

    return flags;
  }

  /**
   * Calculate checksum for integrity
   */
  private calculateChecksum(entry: Omit<AuditLogEntry, 'id' | 'timestamp'>): string {
    const data = JSON.stringify({
      actor: entry.actor,
      action: entry.action,
      resource: entry.resource,
      outcome: entry.outcome
    });

    return crypto.createHash('sha256').update(data).digest('hex');
  }

  /**
   * Check if IP is unusual
   */
  private isUnusualIP(ip: string): boolean {
    // Check against known VPN/proxy/Tor IPs
    // In production, integrate with threat intelligence feeds
    const suspiciousPatterns = [
      /^10\./, // Private range
      /^192\.168\./, // Private range
      /^172\.(1[6-9]|2[0-9]|3[0-1])\./, // Private range
    ];

    return suspiciousPatterns.some(pattern => pattern.test(ip));
  }

  /**
   * Detect anomalies in audit entries
   */
  private isAnomaly(entry: AuditLogEntry, allEntries: AuditLogEntry[]): boolean {
    // Simple anomaly detection - in production use ML models
    const userActions = allEntries.filter(e => 
      e.actor.id === entry.actor.id &&
      Math.abs(e.timestamp.getTime() - entry.timestamp.getTime()) < 3600000 // 1 hour
    );

    // Too many actions in short time
    if (userActions.length > 100) {
      return true;
    }

    // Unusual action for this user
    const commonActions = allEntries
      .filter(e => e.actor.id === entry.actor.id)
      .map(e => e.action);
    
    const actionFrequency = commonActions.filter(a => a === entry.action).length;
    if (actionFrequency === 1 && commonActions.length > 10) {
      return true;
    }

    return false;
  }

  /**
   * Get anomaly severity
   */
  private getAnomalySeverity(entry: AuditLogEntry): 'low' | 'medium' | 'high' | 'critical' {
    const riskScore = entry.risk_score || 0;
    
    if (riskScore > 0.9) return 'critical';
    if (riskScore > 0.7) return 'high';
    if (riskScore > 0.4) return 'medium';
    return 'low';
  }

  /**
   * Export to CSV format
   */
  private exportToCsv(entries: AuditLogEntry[]): Buffer {
    const headers = [
      'ID',
      'Timestamp',
      'Actor ID',
      'Actor Type',
      'Action',
      'Resource Type',
      'Resource ID',
      'Outcome',
      'Risk Score'
    ];

    const rows = entries.map(e => [
      e.id,
      e.timestamp.toISOString(),
      e.actor.id,
      e.actor.type,
      e.action,
      e.resource.type,
      e.resource.id || '',
      e.outcome,
      e.risk_score || ''
    ]);

    const csv = [
      headers.join(','),
      ...rows.map(r => r.map(v => `"${v}"`).join(','))
    ].join('\n');

    return Buffer.from(csv);
  }

  /**
   * Flush batch to storage
   */
  private async flushBatch(): Promise<void> {
    if (this.batchQueue.length === 0) return;

    const batch = [...this.batchQueue];
    this.batchQueue = [];

    // Store in memory (in production, use configured backend)
    for (const entry of batch) {
      this.storage.set(entry.id, entry);
    }

    this.emit('audit:batch-flushed', { count: batch.length });
  }

  /**
   * Start batch processor
   */
  private startBatchProcessor(interval: number): void {
    this.flushTimer = setInterval(() => {
      this.flushBatch().catch(err => {
        this.emit('audit:error', err);
      });
    }, interval);
  }

  /**
   * Start retention cleanup
   */
  private startRetentionCleanup(): void {
    // Run daily
    setInterval(() => {
      this.cleanupOldEntries().catch(err => {
        this.emit('audit:error', err);
      });
    }, 24 * 60 * 60 * 1000);
  }

  /**
   * Clean up entries past retention period
   */
  private async cleanupOldEntries(): Promise<void> {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - this.retentionPolicy.retention_days);

    const entriesToArchive: AuditLogEntry[] = [];
    const entriesToDelete: string[] = [];

    for (const [id, entry] of this.storage) {
      if (entry.timestamp < cutoffDate) {
        if (this.retentionPolicy.archive_enabled) {
          entriesToArchive.push(entry);
        }
        entriesToDelete.push(id);
      }
    }

    // Archive if enabled
    if (entriesToArchive.length > 0 && this.retentionPolicy.archive_enabled) {
      await this.archiveEntries(entriesToArchive);
    }

    // Delete from active storage
    for (const id of entriesToDelete) {
      this.storage.delete(id);
    }

    this.emit('audit:retention-cleanup', {
      archived: entriesToArchive.length,
      deleted: entriesToDelete.length
    });
  }

  /**
   * Archive entries to long-term storage
   */
  private async archiveEntries(entries: AuditLogEntry[]): Promise<void> {
    // In production, implement S3/Glacier upload
    const archiveData = await this.exportLogs('json', {
      limit: Number.MAX_SAFE_INTEGER
    });

    // Encrypt if configured
    const dataToArchive = this.encryptionKey
      ? this.encrypt(archiveData)
      : archiveData;

    // Store archive (implementation depends on backend)
    this.emit('audit:archived', {
      count: entries.length,
      size: dataToArchive.length
    });
  }

  /**
   * Encrypt data for archival
   */
  private encrypt(data: Buffer): Buffer {
    if (!this.encryptionKey) return data;

    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv('aes-256-gcm', this.encryptionKey, iv);
    
    const encrypted = Buffer.concat([
      cipher.update(data),
      cipher.final(),
      cipher.getAuthTag()
    ]);

    return Buffer.concat([iv, encrypted]);
  }

  /**
   * Cleanup resources
   */
  async destroy(): Promise<void> {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }
    
    await this.flushBatch();
    this.removeAllListeners();
  }
}