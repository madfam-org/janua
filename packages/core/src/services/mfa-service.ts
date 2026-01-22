import { EventEmitter } from 'events';
import crypto from 'crypto';
import * as speakeasy from 'speakeasy';
import * as qrcode from 'qrcode';
import { createHash } from 'crypto';

export interface MFAMethod {
  type: 'totp' | 'sms' | 'email' | 'webauthn' | 'hardware' | 'backup_codes';
  enabled: boolean;
  verified: boolean;
  primary: boolean;
  metadata?: Record<string, any>;
}

export interface MFAConfig {
  user_id: string;
  methods: MFAMethod[];
  risk_based_enabled: boolean;
  risk_threshold: number; // 0-1 scale
  grace_period_minutes?: number;
  trusted_devices?: string[];
  trusted_networks?: string[];
  bypass_conditions?: MFABypassCondition[];
}

export interface MFABypassCondition {
  type: 'trusted_device' | 'trusted_network' | 'low_risk' | 'recent_verification';
  value: any;
  expires_at?: Date;
}

export interface MFAChallenge {
  id: string;
  user_id: string;
  session_id: string;
  method: MFAMethod['type'];
  challenge_data?: any;
  created_at: Date;
  expires_at: Date;
  attempts: number;
  max_attempts: number;
  status: 'pending' | 'verified' | 'failed' | 'expired';
}

export interface RiskAssessment {
  score: number; // 0-1 scale
  factors: RiskFactor[];
  requires_mfa: boolean;
  suggested_methods: MFAMethod['type'][];
  bypass_allowed: boolean;
}

export interface RiskFactor {
  type: 'location' | 'device' | 'behavior' | 'time' | 'network' | 'velocity';
  score: number;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

export interface SMSProvider {
  send(phone: string, message: string): Promise<boolean>;
}

export interface HardwareTokenProvider {
  verify(token_id: string, code: string): Promise<boolean>;
  register(user_id: string, token_serial: string): Promise<string>;
}

export class MFAService extends EventEmitter {
  private configs: Map<string, MFAConfig> = new Map();
  private challenges: Map<string, MFAChallenge> = new Map();
  private verificationHistory: Map<string, Date[]> = new Map();
  private trustedDevices: Map<string, Set<string>> = new Map();
  private smsProvider?: SMSProvider;
  private hardwareProvider?: HardwareTokenProvider;

  constructor(
    private readonly config: {
      issuer: string;
      window: number; // TOTP window
      digits?: number; // TOTP digits (6 or 8)
      algorithm?: 'sha1' | 'sha256' | 'sha512';
      smsProvider?: SMSProvider;
      hardwareProvider?: HardwareTokenProvider;
      riskThreshold?: number;
      maxAttempts?: number;
      challengeTTL?: number; // seconds
      gracePeriod?: number; // minutes
    },
    private readonly redisService?: any
  ) {
    super();
    this.smsProvider = config.smsProvider;
    this.hardwareProvider = config.hardwareProvider;
    this.startCleanupTimer();
  }

  /**
   * Generate TOTP secret and provisioning URI
   */
  async generateTOTPSecret(user_id: string, user_email: string): Promise<{
    secret: string;
    qr_code: string;
    provisioning_uri: string;
    backup_codes: string[];
  }> {
    // Generate secret
    const secret = speakeasy.generateSecret({
      name: user_email,
      issuer: this.config.issuer,
      length: 32
    });

    // Generate QR code
    const qrCode = await qrcode.toDataURL(secret.otpauth_url!);

    // Generate backup codes
    const backupCodes = this.generateBackupCodes(10);

    return {
      secret: secret.base32,
      qr_code: qrCode,
      provisioning_uri: secret.otpauth_url!,
      backup_codes: backupCodes
    };
  }

  /**
   * Verify TOTP code
   */
  verifyTOTP(secret: string, token: string): boolean {
    return speakeasy.totp.verify({
      secret,
      encoding: 'base32',
      token,
      window: this.config.window || 2,
      digits: this.config.digits || 6,
      algorithm: this.config.algorithm || 'sha1'
    });
  }

  /**
   * Send SMS code
   */
  async sendSMSCode(user_id: string, phone: string): Promise<MFAChallenge> {
    if (!this.smsProvider) {
      throw new Error('SMS provider not configured');
    }

    // Generate 6-digit code
    const code = Math.floor(100000 + Math.random() * 900000).toString();

    // Create challenge
    const challenge: MFAChallenge = {
      id: crypto.randomUUID(),
      user_id,
      session_id: crypto.randomUUID(),
      method: 'sms',
      challenge_data: { 
        code_hash: this.hashCode(code),
        phone_masked: this.maskPhone(phone)
      },
      created_at: new Date(),
      expires_at: new Date(Date.now() + (this.config.challengeTTL || 300) * 1000),
      attempts: 0,
      max_attempts: this.config.maxAttempts || 3,
      status: 'pending'
    };

    // Store challenge
    this.challenges.set(challenge.id, challenge);

    // Send SMS
    const message = `Your ${this.config.issuer} verification code is: ${code}. Valid for 5 minutes.`;
    const sent = await this.smsProvider.send(phone, message);

    if (!sent) {
      challenge.status = 'failed';
      throw new Error('Failed to send SMS');
    }

    this.emit('mfa:sms-sent', { user_id, phone_masked: challenge.challenge_data.phone_masked });

    return challenge;
  }

  /**
   * Verify SMS code
   */
  verifySMSCode(challenge_id: string, code: string): boolean {
    const challenge = this.challenges.get(challenge_id);
    if (!challenge || challenge.method !== 'sms') {
      return false;
    }

    // Check expiry
    if (challenge.expires_at < new Date()) {
      challenge.status = 'expired';
      return false;
    }

    // Check attempts
    challenge.attempts++;
    if (challenge.attempts > challenge.max_attempts) {
      challenge.status = 'failed';
      this.emit('mfa:max-attempts-exceeded', { challenge_id, user_id: challenge.user_id });
      return false;
    }

    // Verify code
    const codeHash = this.hashCode(code);
    if (codeHash !== challenge.challenge_data.code_hash) {
      return false;
    }

    challenge.status = 'verified';
    this.recordVerification(challenge.user_id, 'sms');
    this.emit('mfa:sms-verified', { user_id: challenge.user_id });

    return true;
  }

  /**
   * Register hardware token
   */
  async registerHardwareToken(user_id: string, token_serial: string): Promise<string> {
    if (!this.hardwareProvider) {
      throw new Error('Hardware token provider not configured');
    }

    const token_id = await this.hardwareProvider.register(user_id, token_serial);
    
    this.emit('mfa:hardware-token-registered', { user_id, token_id });

    return token_id;
  }

  /**
   * Verify hardware token
   */
  async verifyHardwareToken(token_id: string, code: string): Promise<boolean> {
    if (!this.hardwareProvider) {
      throw new Error('Hardware token provider not configured');
    }

    const verified = await this.hardwareProvider.verify(token_id, code);

    if (verified) {
      this.emit('mfa:hardware-token-verified', { token_id });
    }

    return verified;
  }

  /**
   * Assess risk and determine MFA requirements
   */
  async assessRisk(context: {
    user_id: string;
    session_id: string;
    ip_address: string;
    user_agent: string;
    location?: { lat: number; lon: number; country?: string };
    device_fingerprint?: string;
    action: string;
  }): Promise<RiskAssessment> {
    const factors: RiskFactor[] = [];
    let totalScore = 0;

    // 1. Location risk
    const locationRisk = await this.assessLocationRisk(context);
    if (locationRisk) {
      factors.push(locationRisk);
      totalScore += locationRisk.score * 0.3; // 30% weight
    }

    // 2. Device risk
    const deviceRisk = this.assessDeviceRisk(context);
    if (deviceRisk) {
      factors.push(deviceRisk);
      totalScore += deviceRisk.score * 0.25; // 25% weight
    }

    // 3. Behavioral risk
    const behaviorRisk = this.assessBehaviorRisk(context);
    if (behaviorRisk) {
      factors.push(behaviorRisk);
      totalScore += behaviorRisk.score * 0.2; // 20% weight
    }

    // 4. Time-based risk
    const timeRisk = this.assessTimeRisk(context);
    if (timeRisk) {
      factors.push(timeRisk);
      totalScore += timeRisk.score * 0.15; // 15% weight
    }

    // 5. Network risk
    const networkRisk = this.assessNetworkRisk(context);
    if (networkRisk) {
      factors.push(networkRisk);
      totalScore += networkRisk.score * 0.1; // 10% weight
    }

    // Determine if MFA is required
    const threshold = this.config.riskThreshold || 0.5;
    const requiresMFA = totalScore > threshold;

    // Suggest MFA methods based on risk level
    const suggestedMethods = this.suggestMFAMethods(totalScore);

    // Check bypass conditions
    const bypassAllowed = await this.checkBypassConditions(context.user_id, context);

    return {
      score: Math.min(totalScore, 1.0),
      factors,
      requires_mfa: requiresMFA && !bypassAllowed,
      suggested_methods: suggestedMethods,
      bypass_allowed: bypassAllowed
    };
  }

  /**
   * Assess location risk
   */
  private async assessLocationRisk(context: any): Promise<RiskFactor | null> {
    if (!context.location) return null;

    // Check for VPN/Proxy
    const isVPN = await this.detectVPN(context.ip_address);
    if (isVPN) {
      return {
        type: 'location',
        score: 0.7,
        description: 'VPN/Proxy detected',
        severity: 'high'
      };
    }

    // Check for unusual country
    const userHistory = this.getUserLocationHistory(context.user_id);
    if (userHistory.length > 0 && context.location.country) {
      const knownCountries = new Set(userHistory.map(h => h.country));
      if (!knownCountries.has(context.location.country)) {
        return {
          type: 'location',
          score: 0.6,
          description: `Login from new country: ${context.location.country}`,
          severity: 'medium'
        };
      }
    }

    // Check for impossible travel
    const lastLocation = userHistory[userHistory.length - 1];
    if (lastLocation) {
      const timeDiff = (Date.now() - lastLocation.timestamp.getTime()) / 3600000; // hours
      const distance = this.calculateDistance(
        lastLocation.lat, 
        lastLocation.lon,
        context.location.lat,
        context.location.lon
      );
      const velocity = distance / timeDiff;

      if (velocity > 900) { // Faster than commercial flight
        return {
          type: 'velocity',
          score: 0.95,
          description: 'Impossible travel detected',
          severity: 'critical'
        };
      }
    }

    return null;
  }

  /**
   * Assess device risk
   */
  private assessDeviceRisk(context: any): RiskFactor | null {
    if (!context.device_fingerprint) return null;

    const trustedDevices = this.trustedDevices.get(context.user_id);
    
    if (!trustedDevices || !trustedDevices.has(context.device_fingerprint)) {
      return {
        type: 'device',
        score: 0.5,
        description: 'Login from unrecognized device',
        severity: 'medium'
      };
    }

    // Check for suspicious user agent
    if (this.isSuspiciousUserAgent(context.user_agent)) {
      return {
        type: 'device',
        score: 0.4,
        description: 'Suspicious user agent detected',
        severity: 'low'
      };
    }

    return null;
  }

  /**
   * Assess behavioral risk
   */
  private assessBehaviorRisk(context: any): RiskFactor | null {
    // Check for rapid authentication attempts
    const recentAttempts = this.getRecentVerificationAttempts(context.user_id);
    
    if (recentAttempts > 5) {
      return {
        type: 'behavior',
        score: 0.8,
        description: 'Unusual authentication pattern detected',
        severity: 'high'
      };
    }

    // Check for sensitive action
    const sensitiveActions = ['payment', 'password_change', 'mfa_disable', 'api_key_create'];
    if (sensitiveActions.includes(context.action)) {
      return {
        type: 'behavior',
        score: 0.6,
        description: `Sensitive action: ${context.action}`,
        severity: 'medium'
      };
    }

    return null;
  }

  /**
   * Assess time-based risk
   */
  private assessTimeRisk(context: any): RiskFactor | null {
    const hour = new Date().getHours();
    
    // Check for unusual hours (midnight to 6 AM)
    if (hour >= 0 && hour < 6) {
      return {
        type: 'time',
        score: 0.3,
        description: 'Login during unusual hours',
        severity: 'low'
      };
    }

    return null;
  }

  /**
   * Assess network risk
   */
  private assessNetworkRisk(context: any): RiskFactor | null {
    // Check for known malicious IPs
    if (this.isMaliciousIP(context.ip_address)) {
      return {
        type: 'network',
        score: 0.9,
        description: 'Known malicious IP address',
        severity: 'critical'
      };
    }

    // Check for Tor exit node
    if (this.isTorExitNode(context.ip_address)) {
      return {
        type: 'network',
        score: 0.7,
        description: 'Tor network detected',
        severity: 'high'
      };
    }

    return null;
  }

  /**
   * Suggest MFA methods based on risk score
   */
  private suggestMFAMethods(riskScore: number): MFAMethod['type'][] {
    if (riskScore > 0.8) {
      // Very high risk - require multiple factors
      return ['hardware', 'totp', 'sms'];
    } else if (riskScore > 0.6) {
      // High risk - require strong factor
      return ['hardware', 'totp'];
    } else if (riskScore > 0.4) {
      // Medium risk - standard MFA
      return ['totp', 'sms'];
    } else {
      // Low risk - any method
      return ['totp', 'sms', 'email'];
    }
  }

  /**
   * Check bypass conditions
   */
  private async checkBypassConditions(user_id: string, context: any): Promise<boolean> {
    const config = this.configs.get(user_id);
    if (!config || !config.bypass_conditions) return false;

    for (const condition of config.bypass_conditions) {
      switch (condition.type) {
        case 'trusted_device': {
          const trustedDevices = this.trustedDevices.get(user_id);
          if (trustedDevices?.has(context.device_fingerprint)) {
            return true;
          }
          break;
        }

        case 'trusted_network':
          if (config.trusted_networks?.includes(context.ip_address)) {
            return true;
          }
          break;

        case 'low_risk': {
          const assessment = await this.assessRisk(context);
          if (assessment.score < 0.3) {
            return true;
          }
          break;
        }

        case 'recent_verification': {
          const lastVerification = this.getLastVerification(user_id);
          if (lastVerification) {
            const gracePeriod = config.grace_period_minutes || this.config.gracePeriod || 15;
            const elapsed = (Date.now() - lastVerification.getTime()) / 60000; // minutes
            if (elapsed < gracePeriod) {
              return true;
            }
          }
          break;
        }
      }
    }

    return false;
  }

  /**
   * Trust a device
   */
  /**
   * Register a trusted device
   */
  async registerTrustedDevice(
    user_id: string,
    deviceInfo: {
      device_fingerprint: string;
      user_agent?: string;
      ip?: string;
      name?: string;
    }
  ): Promise<{
    id: string;
    user_id: string;
    device_fingerprint: string;
    trusted: boolean;
    expires_at: Date;
    created_at: Date;
  }> {
    const deviceId = `dev_${Date.now()}_${Math.random().toString(36).substring(7)}`;
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 30); // 30 days default
    const createdAt = new Date();

    const device = {
      id: deviceId,
      user_id,
      device_fingerprint: deviceInfo.device_fingerprint,
      user_agent: deviceInfo.user_agent || '',
      ip: deviceInfo.ip || '',
      name: deviceInfo.name || 'Unknown Device',
      trusted: true,
      expires_at: expiresAt,
      created_at: createdAt
    };

    // Store in Redis if available
    if (this.redisService) {
      try {
        await this.redisService.hset(
          `trusted_devices:${user_id}`,
          deviceInfo.device_fingerprint,
          JSON.stringify(device)
        );
        
        // Set expiration
        await this.redisService.expire(
          `trusted_devices:${user_id}`,
          30 * 24 * 60 * 60
        );
      } catch (error) {
        console.error('Error registering trusted device:', error);
      }
    }

    // Store in memory
    if (!this.trustedDevices.has(user_id)) {
      this.trustedDevices.set(user_id, new Set());
    }
    this.trustedDevices.get(user_id)!.add(deviceInfo.device_fingerprint);

    this.emit('mfa:device-registered', device);

    return {
      id: deviceId,
      user_id,
      device_fingerprint: deviceInfo.device_fingerprint,
      trusted: true,
      expires_at: expiresAt,
      created_at: createdAt
    };
  }

  async trustDevice(user_id: string, device_fingerprint: string, duration_days: number = 30): Promise<void> {
    // Store in memory
    if (!this.trustedDevices.has(user_id)) {
      this.trustedDevices.set(user_id, new Set());
    }
    this.trustedDevices.get(user_id)!.add(device_fingerprint);
    
    // Store in Redis if available
    if (this.redisService) {
      const expiresAt = new Date();
      expiresAt.setDate(expiresAt.getDate() + duration_days);
      
      const deviceData = {
        fingerprint: device_fingerprint,
        trustedAt: new Date().toISOString(),
        expiresAt: expiresAt.toISOString(),
        duration_days
      };

      try {
        await this.redisService.hset(
          `trusted_devices:${user_id}`,
          device_fingerprint,
          JSON.stringify(deviceData)
        );
        
        // Set expiration on the entire hash if this is the first device
        await this.redisService.expire(
          `trusted_devices:${user_id}`,
          duration_days * 24 * 60 * 60
        );
      } catch (error) {
        console.error('Error storing trusted device in Redis:', error);
      }
    } else {
      // Schedule removal for in-memory store
      setTimeout(() => {
        this.trustedDevices.get(user_id)?.delete(device_fingerprint);
      }, duration_days * 24 * 60 * 60 * 1000);
    }

    this.emit('mfa:device-trusted', { user_id, device_fingerprint, duration_days });
  }

  /**
   * Check if device is trusted
   */
  async isTrustedDevice(user_id: string, device_fingerprint: string): Promise<boolean> {
    if (!this.redisService) {
      // Fallback to in-memory check
      return this.trustedDevices.get(user_id)?.has(device_fingerprint) || false;
    }

    try {
      const device = await this.redisService.hget(`trusted_devices:${user_id}`, device_fingerprint);
      if (!device) return false;

      const deviceData = JSON.parse(device);
      const expiresAt = new Date(deviceData.expiresAt);
      
      // Check if device trust has expired
      if (expiresAt < new Date()) {
        await this.redisService.hdel(`trusted_devices:${user_id}`, device_fingerprint);
        return false;
      }

      return true;
    } catch (error) {
      console.error('Error checking trusted device:', error);
      return false;
    }
  }

  /**
   * Revoke trusted device
   */
  async revokeTrustedDevice(user_id: string, device_fingerprint: string): Promise<boolean> {
    // Remove from in-memory store
    this.trustedDevices.get(user_id)?.delete(device_fingerprint);

    if (!this.redisService) {
      return true;
    }

    try {
      const result = await this.redisService.hdel(`trusted_devices:${user_id}`, device_fingerprint);
      this.emit('mfa:device-revoked', { user_id, device_fingerprint });
      return result > 0;
    } catch (error) {
      console.error('Error revoking trusted device:', error);
      return false;
    }
  }

  /**
   * Generate backup codes
   */
  private generateBackupCodes(count: number): string[] {
    const codes: string[] = [];
    
    for (let i = 0; i < count; i++) {
      const code = crypto.randomBytes(4).toString('hex').toUpperCase();
      codes.push(`${code.slice(0, 4)}-${code.slice(4)}`);
    }

    return codes;
  }

  /**
   * Hash code for storage
   */
  private hashCode(code: string): string {
    return createHash('sha256').update(code).digest('hex');
  }

  /**
   * Mask phone number
   */
  private maskPhone(phone: string): string {
    if (phone.length < 4) return '****';
    return `****${phone.slice(-4)}`;
  }

  /**
   * Calculate distance between coordinates
   */
  private calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371; // Earth radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
      Math.sin(dLat/2) * Math.sin(dLat/2) +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  }

  /**
   * Detect VPN/Proxy (simplified - in production use IP intelligence service)
   */
  private async detectVPN(_ip: string): Promise<boolean> {
    // Check common VPN/proxy IP ranges
    const _vpnRanges = [
      '10.0.0.0/8',
      '172.16.0.0/12',
      '192.168.0.0/16'
    ];

    // In production, use services like IPQualityScore, MaxMind, etc.
    return false;
  }

  /**
   * Check if IP is malicious (simplified)
   */
  private isMaliciousIP(ip: string): boolean {
    // In production, check against threat intelligence feeds
    return false;
  }

  /**
   * Check if IP is Tor exit node
   */
  private isTorExitNode(ip: string): boolean {
    // In production, check against Tor exit node list
    return false;
  }

  /**
   * Check for suspicious user agent
   */
  private isSuspiciousUserAgent(userAgent: string): boolean {
    const suspicious = [
      'bot', 'crawler', 'spider', 'scraper',
      'curl', 'wget', 'python-requests'
    ];

    const lowerUA = userAgent.toLowerCase();
    return suspicious.some(s => lowerUA.includes(s));
  }

  /**
   * Get user location history (simplified)
   */
  private getUserLocationHistory(user_id: string): any[] {
    // In production, fetch from database
    return [];
  }

  /**
   * Get recent verification attempts
   */
  private getRecentVerificationAttempts(user_id: string): number {
    const history = this.verificationHistory.get(user_id) || [];
    const recent = history.filter(date => 
      Date.now() - date.getTime() < 3600000 // Last hour
    );
    return recent.length;
  }

  /**
   * Get last verification time
   */
  private getLastVerification(user_id: string): Date | null {
    const history = this.verificationHistory.get(user_id);
    if (!history || history.length === 0) return null;
    return history[history.length - 1];
  }

  /**
   * Record successful verification
   */
  private recordVerification(user_id: string, method: MFAMethod['type']): void {
    if (!this.verificationHistory.has(user_id)) {
      this.verificationHistory.set(user_id, []);
    }
    
    const history = this.verificationHistory.get(user_id)!;
    history.push(new Date());
    
    // Keep only last 100 entries
    if (history.length > 100) {
      history.shift();
    }
  }

  /**
   * Cleanup expired challenges
   */
  private startCleanupTimer(): void {
    setInterval(() => {
      const now = new Date();
      
      for (const [id, challenge] of this.challenges) {
        if (challenge.expires_at < now) {
          challenge.status = 'expired';
          this.challenges.delete(id);
        }
      }
    }, 60000); // Every minute
  }

  /**
   * Get user's MFA configuration
   */
  getUserConfig(user_id: string): MFAConfig | undefined {
    return this.configs.get(user_id);
  }

  /**
   * Update user's MFA configuration
   */
  updateUserConfig(user_id: string, config: Partial<MFAConfig>): void {
    const existing = this.configs.get(user_id) || {
      user_id,
      methods: [],
      risk_based_enabled: false,
      risk_threshold: 0.5
    };

    this.configs.set(user_id, { ...existing, ...config });
    this.emit('mfa:config-updated', { user_id, config });
  }

  /**
   * Get statistics
   */
  getStatistics(): {
    total_users: number;
    total_challenges: number;
    active_challenges: number;
    trusted_devices: number;
    verification_rate: number;
  } {
    let activeCount = 0;
    let verifiedCount = 0;
    let totalDevices = 0;

    for (const challenge of this.challenges.values()) {
      if (challenge.status === 'pending') {
        activeCount++;
      }
      if (challenge.status === 'verified') {
        verifiedCount++;
      }
    }

    for (const devices of this.trustedDevices.values()) {
      totalDevices += devices.size;
    }

    return {
      total_users: this.configs.size,
      total_challenges: this.challenges.size,
      active_challenges: activeCount,
      trusted_devices: totalDevices,
      verification_rate: this.challenges.size > 0 ? verifiedCount / this.challenges.size : 0
    };
  }
}