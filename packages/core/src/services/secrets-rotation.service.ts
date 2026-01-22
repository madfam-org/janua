/**
 * Automated Secrets Rotation Service
 * Handles automatic rotation of JWT keys, API keys, and encryption keys
 */

import { EventEmitter } from 'events';
import crypto from 'crypto';
import { CronJob } from 'cron';
import { KeyManagementService } from './kms.service';
import { AuditService } from './audit.service';
import { ConfigService } from './config.service';

import { createLogger } from '../utils/logger';

const logger = createLogger('SecretsRotation');

export interface RotationConfig {
  rotationInterval: string; // Cron expression
  keyType: 'jwt' | 'api' | 'encryption' | 'signing';
  algorithm: string;
  keySize: number;
  gracePeriod: number; // Minutes to keep old key active
  notificationChannels: string[];
}

export interface SecretMetadata {
  id: string;
  keyType: string;
  version: number;
  createdAt: Date;
  expiresAt: Date;
  status: 'active' | 'rotating' | 'expired' | 'revoked';
  algorithm: string;
  checksum: string;
}

export class SecretsRotationService extends EventEmitter {
  private rotationJobs: Map<string, CronJob> = new Map();
  private activeSecrets: Map<string, SecretMetadata> = new Map();
  private rotationHistory: SecretMetadata[] = [];
  
  constructor(
    private kms: KeyManagementService,
    private audit: AuditService,
    private config: ConfigService
  ) {
    super();
    this.initializeRotationSchedules();
  }

  /**
   * Initialize rotation schedules from configuration
   */
  private async initializeRotationSchedules(): Promise<void> {
    try {
      const rotationConfig = this.config.get('secrets');
      if (!rotationConfig || typeof rotationConfig !== 'object') {
        logger.info('No secrets rotation configuration found, skipping initialization');
        return;
      }

      const rotation = (rotationConfig as any).rotation;
      if (!rotation || !Array.isArray(rotation)) {
        logger.info('No rotation schedules configured');
        return;
      }

      const rotationConfigs = rotation as RotationConfig[];
      
      for (const config of rotationConfigs) {
        await this.scheduleRotation(config);
      }

      // Set up monitoring
      this.startHealthCheck();
    } catch (error) {
      logger.error('Failed to initialize rotation schedules', error as Error);
      this.emit('initialization:error', error as Error);
    }
  }

  /**
   * Schedule automatic rotation for a secret type
   */
  public async scheduleRotation(config: RotationConfig): Promise<void> {
    const jobId = `${config.keyType}-rotation`;
    
    // Clear existing job if any
    if (this.rotationJobs.has(jobId)) {
      this.rotationJobs.get(jobId)?.stop();
    }

    const job = new CronJob(
      config.rotationInterval,
      async () => {
        try {
          await this.rotateSecret(config);
        } catch (error) {
          this.emit('rotation:error', { config, error });
          await this.handleRotationError(config, error as Error);
        }
      },
      null,
      true,
      'UTC'
    );

    this.rotationJobs.set(jobId, job);
    
    await this.audit.log({
      action: 'secret_rotation_scheduled',
      actor: {
        id: 'system',
        type: 'system'
      },
      resource: {
        type: 'secret',
        id: config.keyType
      },
      outcome: 'success',
      details: {
        keyType: config.keyType,
        interval: config.rotationInterval
      }
    });
  }

  /**
   * Rotate a secret with zero-downtime strategy
   */
  public async rotateSecret(config: RotationConfig): Promise<SecretMetadata> {
    this.emit('rotation:started', config);
    
    // Generate new secret
    const newSecret = await this.generateSecret(config);
    
    // Store in KMS
    await this.kms.storeKey({
      keyId: newSecret.id,
      keyMaterial: newSecret.keyMaterial,
      metadata: newSecret
    });

    // Implement grace period for old key
    if (config.gracePeriod > 0) {
      await this.implementGracePeriod(config, newSecret);
    }

    // Update active secrets
    const oldSecret = this.activeSecrets.get(config.keyType);
    this.activeSecrets.set(config.keyType, newSecret);
    
    // Archive old secret
    if (oldSecret) {
      oldSecret.status = 'expired';
      this.rotationHistory.push(oldSecret);
    }

    // Notify relevant services
    await this.notifyRotation(config, newSecret);
    
    // Audit the rotation
    await this.audit.log({
      action: 'secret_rotated',
      actor: {
        id: 'system',
        type: 'system'
      },
      resource: {
        type: 'secret',
        id: config.keyType
      },
      outcome: 'success',
      details: {
        keyType: config.keyType,
        oldVersion: oldSecret?.version,
        newVersion: newSecret.version,
        algorithm: config.algorithm
      }
    });

    this.emit('rotation:completed', { config, secret: newSecret });
    
    return newSecret;
  }

  /**
   * Generate a new secret based on configuration
   */
  private async generateSecret(config: RotationConfig): Promise<SecretMetadata & { keyMaterial: string }> {
    let keyMaterial: string;
    
    switch (config.keyType) {
      case 'jwt':
        keyMaterial = await this.generateJWTKey(config);
        break;
      case 'api':
        keyMaterial = this.generateAPIKey(config.keySize);
        break;
      case 'encryption':
        keyMaterial = await this.generateEncryptionKey(config);
        break;
      case 'signing':
        keyMaterial = await this.generateSigningKey(config);
        break;
      default:
        throw new Error(`Unknown key type: ${config.keyType}`);
    }

    const metadata: SecretMetadata = {
      id: crypto.randomUUID(),
      keyType: config.keyType,
      version: Date.now(),
      createdAt: new Date(),
      expiresAt: this.calculateExpiration(config),
      status: 'active',
      algorithm: config.algorithm,
      checksum: this.calculateChecksum(keyMaterial)
    };

    return { ...metadata, keyMaterial };
  }

  /**
   * Generate JWT signing key
   */
  private async generateJWTKey(config: RotationConfig): Promise<string> {
    const { privateKey, publicKey } = crypto.generateKeyPairSync(
      config.algorithm as any,
      {
        modulusLength: config.keySize,
        publicKeyEncoding: {
          type: 'spki',
          format: 'pem'
        },
        privateKeyEncoding: {
          type: 'pkcs8',
          format: 'pem'
        }
      }
    );

    // Store public key separately for verification
    await this.kms.storePublicKey({
      keyId: `${config.keyType}-public`,
      keyMaterial: publicKey
    });

    return privateKey;
  }

  /**
   * Generate API key
   */
  private generateAPIKey(length: number = 32): string {
    return crypto.randomBytes(length).toString('base64url');
  }

  /**
   * Generate encryption key
   */
  private async generateEncryptionKey(config: RotationConfig): Promise<string> {
    const key = crypto.randomBytes(config.keySize / 8);
    
    // Wrap with KMS master key if available
    if (this.kms.hasMasterKey()) {
      return await this.kms.wrapKey(key);
    }
    
    return key.toString('base64');
  }

  /**
   * Generate signing key for webhooks/HMAC
   */
  private async generateSigningKey(config: RotationConfig): Promise<string> {
    return crypto.randomBytes(config.keySize / 8).toString('base64');
  }

  /**
   * Implement grace period for smooth transition
   */
  private async implementGracePeriod(
    config: RotationConfig,
    newSecret: SecretMetadata
  ): Promise<void> {
    const gracePeriodMs = config.gracePeriod * 60 * 1000;
    
    // Keep both old and new keys active during grace period
    this.emit('rotation:grace-period', {
      keyType: config.keyType,
      duration: config.gracePeriod
    });

    // Schedule old key deactivation
    setTimeout(async () => {
      await this.deactivateOldKey(config.keyType);
      this.emit('rotation:grace-period-ended', config.keyType);
    }, gracePeriodMs);
  }

  /**
   * Deactivate old key after grace period
   */
  private async deactivateOldKey(keyType: string): Promise<void> {
    const oldKeys = this.rotationHistory.filter(
      s => s.keyType === keyType && s.status === 'active'
    );

    for (const key of oldKeys) {
      key.status = 'expired';
      await this.kms.revokeKey(key.id);
    }

    await this.audit.log({
      action: 'old_keys_deactivated',
      actor: {
        id: 'system',
        type: 'system'
      },
      resource: {
        type: 'secret',
        id: keyType
      },
      outcome: 'success',
      details: {
        keyType,
        count: oldKeys.length
      }
    });
  }

  /**
   * Notify services about rotation
   */
  private async notifyRotation(
    config: RotationConfig,
    newSecret: SecretMetadata
  ): Promise<void> {
    const notifications = config.notificationChannels.map(channel => 
      this.sendNotification(channel, {
        event: 'secret_rotated',
        keyType: config.keyType,
        version: newSecret.version,
        expiresAt: newSecret.expiresAt
      })
    );

    await Promise.all(notifications);
  }

  /**
   * Send notification to a channel
   */
  private async sendNotification(channel: string, data: any): Promise<void> {
    // Implementation would integrate with various notification services
    // Slack, email, webhook, etc.
    this.emit('notification:sent', { channel, data });
  }

  /**
   * Handle rotation errors
   */
  private async handleRotationError(config: RotationConfig, error: any): Promise<void> {
    await this.audit.log({
      action: 'secret_rotation_failed',
      actor: {
        id: 'system',
        type: 'system'
      },
      resource: {
        type: 'secret',
        id: config.keyType
      },
      outcome: 'failure',
      details: {
        keyType: config.keyType,
        error: error.message
      }
    });

    // Implement retry logic
    const retryDelay = 5 * 60 * 1000; // 5 minutes
    setTimeout(() => {
      this.rotateSecret(config).catch(err => {
        // If retry fails, alert operations team
        this.emit('rotation:critical-failure', { config, error: err });
      });
    }, retryDelay);
  }

  /**
   * Calculate expiration date based on rotation interval
   */
  private calculateExpiration(config: RotationConfig): Date {
    const now = new Date();
    // Parse cron expression to determine next rotation
    // For simplicity, using a default of 90 days
    const expirationMs = 90 * 24 * 60 * 60 * 1000;
    return new Date(now.getTime() + expirationMs);
  }

  /**
   * Calculate checksum for verification
   */
  private calculateChecksum(data: string): string {
    return crypto.createHash('sha256').update(data).digest('hex');
  }

  /**
   * Monitor rotation health
   */
  private startHealthCheck(): void {
    setInterval(() => {
      this.checkRotationHealth();
    }, 60 * 60 * 1000); // Every hour
  }

  /**
   * Check rotation system health
   */
  private async checkRotationHealth(): Promise<void> {
    const now = new Date();
    
    for (const [keyType, secret] of this.activeSecrets) {
      const timeToExpiry = secret.expiresAt.getTime() - now.getTime();
      const daysToExpiry = timeToExpiry / (24 * 60 * 60 * 1000);
      
      if (daysToExpiry < 7) {
        this.emit('rotation:expiry-warning', {
          keyType,
          daysToExpiry: Math.floor(daysToExpiry)
        });
      }

      if (daysToExpiry < 0) {
        this.emit('rotation:expired', { keyType });
        // Trigger immediate rotation
        try {
          const secretsConfig = this.config.get('secrets');
          if (secretsConfig && typeof secretsConfig === 'object') {
            const rotation = (secretsConfig as any).rotation;
            if (rotation && Array.isArray(rotation)) {
              const config = rotation.find((r: any) => r.keyType === keyType) as RotationConfig;
              if (config) {
                await this.rotateSecret(config);
              }
            }
          }
        } catch (error) {
          logger.error(`Failed to auto-rotate expired key ${keyType}`, error as Error);
        }
      }
    }
  }

  /**
   * Get current active secret for a key type
   */
  public getActiveSecret(keyType: string): SecretMetadata | undefined {
    return this.activeSecrets.get(keyType);
  }

  /**
   * Get rotation history
   */
  public getRotationHistory(keyType?: string): SecretMetadata[] {
    if (keyType) {
      return this.rotationHistory.filter(s => s.keyType === keyType);
    }
    return this.rotationHistory;
  }

  /**
   * Manually trigger rotation
   */
  public async manualRotation(keyType: string): Promise<SecretMetadata> {
    try {
      const secretsConfig = this.config.get('secrets');
      if (!secretsConfig || typeof secretsConfig !== 'object') {
        throw new Error('No secrets configuration found');
      }

      const rotation = (secretsConfig as any).rotation;
      if (!rotation || !Array.isArray(rotation)) {
        throw new Error('No rotation configuration found');
      }

      const config = rotation.find((r: any) => r.keyType === keyType) as RotationConfig;
      
      if (!config) {
        throw new Error(`No rotation configuration found for key type: ${keyType}`);
      }
      
      return await this.rotateSecret(config);
    } catch (error) {
      throw new Error(`Failed to manually rotate ${keyType}: ${(error as Error).message}`);
    }
  }

  /**
   * Stop all rotation jobs
   */
  public stopAllRotations(): void {
    for (const [jobId, job] of this.rotationJobs) {
      job.stop();
      this.rotationJobs.delete(jobId);
    }
    
    this.emit('rotation:all-stopped');
  }
}