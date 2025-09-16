import { EventEmitter } from 'events';
import { 
  generateRegistrationOptions, 
  verifyRegistrationResponse,
  generateAuthenticationOptions,
  verifyAuthenticationResponse,
  VerifiedRegistrationResponse,
  VerifiedAuthenticationResponse
} from '@simplewebauthn/server';
import { 
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  AuthenticatorDevice
} from '@simplewebauthn/typescript-types';
import { getRedis, RedisService } from './redis.service';

interface WebAuthnConfig {
  rpName: string;
  rpID: string;
  origin: string | string[];
  challengeTTL?: number; // seconds, default 300 (5 minutes)
  userVerification?: 'required' | 'preferred' | 'discouraged';
  attestationType?: 'none' | 'indirect' | 'direct';
  authenticatorAttachment?: 'platform' | 'cross-platform' | null;
  residentKey?: 'required' | 'preferred' | 'discouraged';
}

interface Passkey {
  id: string;
  userId: string;
  credentialID: string;
  credentialPublicKey: string;
  counter: number;
  name?: string;
  transports?: AuthenticatorTransport[];
  deviceType: 'platform' | 'cross-platform' | 'unknown';
  backedUp: boolean;
  createdAt: Date;
  lastUsedAt?: Date;
}

type AuthenticatorTransport = 'usb' | 'nfc' | 'ble' | 'internal';

export class WebAuthnService extends EventEmitter {
  private config: WebAuthnConfig;
  private redis: RedisService;
  private passkeys: Map<string, Passkey> = new Map();
  private userPasskeys: Map<string, Set<string>> = new Map();
  
  constructor(config: WebAuthnConfig) {
    super();
    this.config = {
      challengeTTL: 300,
      userVerification: 'preferred',
      attestationType: 'none',
      authenticatorAttachment: null,
      residentKey: 'preferred',
      ...config
    };
    this.redis = getRedis();
  }
  
  // Registration Flow
  async generateRegistrationOptions(
    userId: string,
    userName: string,
    userDisplayName?: string
  ): Promise<PublicKeyCredentialCreationOptionsJSON> {
    // Get existing passkeys to exclude
    const existingPasskeys = await this.getUserPasskeys(userId);
    const excludeCredentials = existingPasskeys.map(passkey => ({
      id: Buffer.from(passkey.credentialID, 'base64'),
      type: 'public-key' as const,
      transports: passkey.transports
    }));
    
    // Generate options
    const options = await generateRegistrationOptions({
      rpName: this.config.rpName,
      rpID: this.config.rpID,
      userID: userId,
      userName,
      userDisplayName: userDisplayName || userName,
      attestationType: this.config.attestationType,
      excludeCredentials,
      authenticatorSelection: {
        authenticatorAttachment: this.config.authenticatorAttachment,
        residentKey: this.config.residentKey,
        userVerification: this.config.userVerification
      },
      supportedAlgorithmIDs: [-7, -257], // ES256, RS256
      timeout: this.config.challengeTTL ? this.config.challengeTTL * 1000 : 300000
    });
    
    // Store challenge in Redis
    await this.redis.storeWebAuthnChallenge(
      userId,
      options.challenge,
      'registration',
      this.config.challengeTTL
    );
    
    // Emit event
    this.emit('registration_options_generated', {
      userId,
      timestamp: new Date()
    });
    
    return options;
  }
  
  async verifyRegistration(
    userId: string,
    credential: any,
    name?: string
  ): Promise<{ verified: boolean; passkey?: Passkey }> {
    // Get stored challenge from Redis
    const expectedChallenge = await this.redis.getWebAuthnChallenge(userId, 'registration');
    
    if (!expectedChallenge) {
      this.emit('registration_failed', {
        userId,
        reason: 'No challenge found or expired',
        timestamp: new Date()
      });
      return { verified: false };
    }
    
    // Verify the registration
    let verification: VerifiedRegistrationResponse;
    try {
      verification = await verifyRegistrationResponse({
        response: credential,
        expectedChallenge,
        expectedOrigin: this.config.origin,
        expectedRPID: this.config.rpID,
        requireUserVerification: this.config.userVerification === 'required'
      });
    } catch (error: any) {
      this.emit('registration_failed', {
        userId,
        reason: error.message,
        timestamp: new Date()
      });
      return { verified: false };
    }
    
    if (!verification.verified || !verification.registrationInfo) {
      this.emit('registration_failed', {
        userId,
        reason: 'Verification failed',
        timestamp: new Date()
      });
      return { verified: false };
    }
    
    // Create passkey record
    const { registrationInfo } = verification;
    const passkey: Passkey = {
      id: `passkey-${Buffer.from(registrationInfo.credentialID).toString('base64url')}`,
      userId,
      credentialID: Buffer.from(registrationInfo.credentialID).toString('base64'),
      credentialPublicKey: Buffer.from(registrationInfo.credentialPublicKey).toString('base64'),
      counter: registrationInfo.counter,
      name: name || `Passkey ${new Date().toISOString()}`,
      transports: credential.response.transports,
      deviceType: registrationInfo.credentialDeviceType || 'unknown',
      backedUp: registrationInfo.credentialBackedUp || false,
      createdAt: new Date()
    };
    
    // Store passkey
    await this.storePasskey(passkey);
    
    // Emit success event
    this.emit('registration_completed', {
      userId,
      passkeyId: passkey.id,
      deviceType: passkey.deviceType,
      timestamp: new Date()
    });
    
    return { verified: true, passkey };
  }
  
  // Authentication Flow
  async generateAuthenticationOptions(
    userId?: string
  ): Promise<PublicKeyCredentialRequestOptionsJSON> {
    let allowCredentials: any[] = [];
    
    if (userId) {
      // Get user's passkeys
      const userPasskeys = await this.getUserPasskeys(userId);
      allowCredentials = userPasskeys.map(passkey => ({
        id: Buffer.from(passkey.credentialID, 'base64'),
        type: 'public-key' as const,
        transports: passkey.transports
      }));
    }
    
    // Generate options
    const options = await generateAuthenticationOptions({
      rpID: this.config.rpID,
      allowCredentials: allowCredentials.length > 0 ? allowCredentials : undefined,
      userVerification: this.config.userVerification,
      timeout: this.config.challengeTTL ? this.config.challengeTTL * 1000 : 300000
    });
    
    // Store challenge in Redis
    const challengeKey = userId || 'anonymous';
    await this.redis.storeWebAuthnChallenge(
      challengeKey,
      options.challenge,
      'authentication',
      this.config.challengeTTL
    );
    
    // Emit event
    this.emit('authentication_options_generated', {
      userId: userId || 'anonymous',
      timestamp: new Date()
    });
    
    return options;
  }
  
  async verifyAuthentication(
    credential: any,
    userId?: string
  ): Promise<{ verified: boolean; passkey?: Passkey; userId?: string }> {
    // Determine challenge key
    const challengeKey = userId || 'anonymous';
    
    // Get stored challenge from Redis
    const expectedChallenge = await this.redis.getWebAuthnChallenge(challengeKey, 'authentication');
    
    if (!expectedChallenge) {
      this.emit('authentication_failed', {
        reason: 'No challenge found or expired',
        timestamp: new Date()
      });
      return { verified: false };
    }
    
    // Get authenticator device (passkey) by credential ID
    const credentialID = Buffer.from(credential.id, 'base64url').toString('base64');
    const passkey = await this.getPasskeyByCredentialID(credentialID);
    
    if (!passkey) {
      this.emit('authentication_failed', {
        reason: 'Passkey not found',
        timestamp: new Date()
      });
      return { verified: false };
    }
    
    // Build authenticator device object
    const authenticatorDevice: AuthenticatorDevice = {
      credentialID: Buffer.from(passkey.credentialID, 'base64'),
      credentialPublicKey: Buffer.from(passkey.credentialPublicKey, 'base64'),
      counter: passkey.counter,
      transports: passkey.transports as any
    };
    
    // Verify authentication
    let verification: VerifiedAuthenticationResponse;
    try {
      verification = await verifyAuthenticationResponse({
        response: credential,
        expectedChallenge,
        expectedOrigin: this.config.origin,
        expectedRPID: this.config.rpID,
        authenticator: authenticatorDevice,
        requireUserVerification: this.config.userVerification === 'required'
      });
    } catch (error: any) {
      this.emit('authentication_failed', {
        userId: passkey.userId,
        reason: error.message,
        timestamp: new Date()
      });
      return { verified: false };
    }
    
    if (!verification.verified) {
      this.emit('authentication_failed', {
        userId: passkey.userId,
        reason: 'Verification failed',
        timestamp: new Date()
      });
      return { verified: false };
    }
    
    // Update counter and last used time
    passkey.counter = verification.authenticationInfo.newCounter;
    passkey.lastUsedAt = new Date();
    await this.updatePasskey(passkey);
    
    // Emit success event
    this.emit('authentication_completed', {
      userId: passkey.userId,
      passkeyId: passkey.id,
      timestamp: new Date()
    });
    
    return { 
      verified: true, 
      passkey,
      userId: passkey.userId
    };
  }
  
  // Passkey Management
  private async storePasskey(passkey: Passkey): Promise<void> {
    // Store in memory (in production, use database)
    this.passkeys.set(passkey.id, passkey);
    
    // Update user index
    if (!this.userPasskeys.has(passkey.userId)) {
      this.userPasskeys.set(passkey.userId, new Set());
    }
    this.userPasskeys.get(passkey.userId)!.add(passkey.id);
    
    // Store in Redis for persistence
    await this.redis.hset('passkeys', passkey.id, passkey);
    await this.redis.sadd(`user:passkeys:${passkey.userId}`, passkey.id);
  }
  
  private async updatePasskey(passkey: Passkey): Promise<void> {
    this.passkeys.set(passkey.id, passkey);
    await this.redis.hset('passkeys', passkey.id, passkey);
  }
  
  async getPasskey(passkeyId: string): Promise<Passkey | null> {
    // Check memory first
    if (this.passkeys.has(passkeyId)) {
      return this.passkeys.get(passkeyId)!;
    }
    
    // Check Redis
    const passkey = await this.redis.hget<Passkey>('passkeys', passkeyId);
    if (passkey) {
      this.passkeys.set(passkeyId, passkey);
      return passkey;
    }
    
    return null;
  }
  
  private async getPasskeyByCredentialID(credentialID: string): Promise<Passkey | null> {
    // Search in memory
    for (const passkey of this.passkeys.values()) {
      if (passkey.credentialID === credentialID) {
        return passkey;
      }
    }
    
    // Search in Redis
    const allPasskeys = await this.redis.hgetall<Passkey>('passkeys');
    for (const passkey of Object.values(allPasskeys)) {
      if (passkey.credentialID === credentialID) {
        this.passkeys.set(passkey.id, passkey);
        return passkey;
      }
    }
    
    return null;
  }
  
  async getUserPasskeys(userId: string): Promise<Passkey[]> {
    const passkeys: Passkey[] = [];
    
    // Check memory first
    const passkeyIds = this.userPasskeys.get(userId);
    if (passkeyIds) {
      for (const id of passkeyIds) {
        const passkey = this.passkeys.get(id);
        if (passkey) {
          passkeys.push(passkey);
        }
      }
      
      if (passkeys.length > 0) {
        return passkeys;
      }
    }
    
    // Check Redis
    const storedIds = await this.redis.smembers<string>(`user:passkeys:${userId}`);
    for (const id of storedIds) {
      const passkey = await this.getPasskey(id);
      if (passkey) {
        passkeys.push(passkey);
      }
    }
    
    return passkeys;
  }
  
  async deletePasskey(passkeyId: string): Promise<boolean> {
    const passkey = await this.getPasskey(passkeyId);
    if (!passkey) {
      return false;
    }
    
    // Remove from memory
    this.passkeys.delete(passkeyId);
    const userKeys = this.userPasskeys.get(passkey.userId);
    if (userKeys) {
      userKeys.delete(passkeyId);
      if (userKeys.size === 0) {
        this.userPasskeys.delete(passkey.userId);
      }
    }
    
    // Remove from Redis
    await this.redis.hdel('passkeys', passkeyId);
    await this.redis.srem(`user:passkeys:${passkey.userId}`, passkeyId);
    
    // Emit event
    this.emit('passkey_deleted', {
      userId: passkey.userId,
      passkeyId,
      timestamp: new Date()
    });
    
    return true;
  }
  
  async updatePasskeyName(passkeyId: string, name: string): Promise<boolean> {
    const passkey = await this.getPasskey(passkeyId);
    if (!passkey) {
      return false;
    }
    
    passkey.name = name;
    await this.updatePasskey(passkey);
    
    return true;
  }
  
  // Statistics
  async getStats(): Promise<{
    totalPasskeys: number;
    userCount: number;
    deviceTypes: Record<string, number>;
    backedUpCount: number;
  }> {
    const allPasskeys = Array.from(this.passkeys.values());
    const deviceTypes: Record<string, number> = {};
    let backedUpCount = 0;
    
    for (const passkey of allPasskeys) {
      deviceTypes[passkey.deviceType] = (deviceTypes[passkey.deviceType] || 0) + 1;
      if (passkey.backedUp) {
        backedUpCount++;
      }
    }
    
    return {
      totalPasskeys: allPasskeys.length,
      userCount: this.userPasskeys.size,
      deviceTypes,
      backedUpCount
    };
  }
  
  // Cleanup old challenges periodically
  async cleanupExpiredChallenges(): Promise<void> {
    // Redis handles TTL automatically, but we can add additional cleanup if needed
    const pattern = 'webauthn:*';
    const keys = await this.redis.keys(pattern);
    
    for (const key of keys) {
      const ttl = await this.redis.ttl(key);
      if (ttl === -1) {
        // No TTL set, remove if older than challengeTTL
        await this.redis.expire(key, this.config.challengeTTL || 300);
      }
    }
  }
}

// Export factory function
export function createWebAuthnService(config: WebAuthnConfig): WebAuthnService {
  return new WebAuthnService(config);
}