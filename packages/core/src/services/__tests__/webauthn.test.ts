import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { WebAuthnService } from '../webauthn.service';
import { RedisService } from '../redis.service';
import * as simplewebauthn from '@simplewebauthn/server';

// Mock dependencies
jest.mock('../redis.service');
jest.mock('@simplewebauthn/server', () => ({
  generateRegistrationOptions: jest.fn(),
  verifyRegistrationResponse: jest.fn(),
  generateAuthenticationOptions: jest.fn(),
  verifyAuthenticationResponse: jest.fn()
}));

describe('WebAuthnService', () => {
  let webauthnService: WebAuthnService;
  let mockRedisService: jest.Mocked<RedisService>;
  
  const config = {
    rpName: 'Plinto Test',
    rpID: 'localhost',
    origin: 'http://localhost:3000',
    challengeTTL: 300
  };
  
  beforeEach(() => {
    mockRedisService = {
      storeWebAuthnChallenge: jest.fn(),
      getWebAuthnChallenge: jest.fn(),
      hset: jest.fn(),
      hget: jest.fn(),
      hgetall: jest.fn(),
      hdel: jest.fn(),
      sadd: jest.fn(),
      srem: jest.fn(),
      smembers: jest.fn(),
      keys: jest.fn(),
      ttl: jest.fn(),
      expire: jest.fn()
    } as any;
    
    jest.spyOn(require('../redis.service'), 'getRedis').mockReturnValue(mockRedisService);
    
    webauthnService = new WebAuthnService(config);
  });
  
  afterEach(() => {
    jest.clearAllMocks();
  });
  
  describe('Registration Flow', () => {
    it('should generate registration options', async () => {
      const mockOptions = {
        challenge: 'test-challenge',
        rp: { id: 'localhost', name: 'Plinto Test' },
        user: {
          id: Buffer.from('user123'),
          name: 'test@example.com',
          displayName: 'Test User'
        },
        pubKeyCredParams: [],
        timeout: 300000,
        excludeCredentials: [],
        authenticatorSelection: {
          authenticatorAttachment: null,
          residentKey: 'preferred',
          userVerification: 'preferred'
        },
        attestation: 'none'
      };
      
      (simplewebauthn.generateRegistrationOptions as jest.MockedFunction<typeof simplewebauthn.generateRegistrationOptions>).mockResolvedValueOnce(mockOptions as any);
      mockRedisService.smembers.mockResolvedValueOnce([]);
      
      const options = await webauthnService.generateRegistrationOptions(
        'user123',
        'test@example.com',
        'Test User'
      );
      
      expect(options).toBeDefined();
      expect(options.challenge).toBe('test-challenge');
      expect(options.rp.id).toBe('localhost');
      expect(mockRedisService.storeWebAuthnChallenge).toHaveBeenCalledWith(
        'user123',
        'test-challenge',
        'registration',
        300
      );
    });
    
    it('should exclude existing passkeys in registration options', async () => {
      const existingPasskey = {
        id: 'passkey-123',
        userId: 'user123',
        credentialID: 'cred123',
        credentialPublicKey: 'pubkey123',
        counter: 0,
        deviceType: 'platform',
        backedUp: false,
        createdAt: new Date()
      };
      
      mockRedisService.smembers.mockResolvedValueOnce(['passkey-123']);
      mockRedisService.hget.mockResolvedValueOnce(existingPasskey);
      
      const mockOptions = {
        challenge: 'test-challenge',
        excludeCredentials: [{
          id: Buffer.from('cred123', 'base64'),
          type: 'public-key'
        }]
      };
      
      (simplewebauthn.generateRegistrationOptions as jest.MockedFunction<typeof simplewebauthn.generateRegistrationOptions>).mockResolvedValueOnce(mockOptions as any);
      
      const options = await webauthnService.generateRegistrationOptions(
        'user123',
        'test@example.com'
      );
      
      expect(options.excludeCredentials).toHaveLength(1);
    });
    
    it('should verify registration and create passkey', async () => {
      const credential = {
        id: 'cred123',
        response: {
          clientDataJSON: 'client-data',
          attestationObject: 'attestation',
          transports: ['usb', 'nfc']
        }
      };
      
      mockRedisService.getWebAuthnChallenge.mockResolvedValueOnce('stored-challenge');
      
      (simplewebauthn.verifyRegistrationResponse as jest.MockedFunction<typeof simplewebauthn.verifyRegistrationResponse>).mockResolvedValueOnce({
        verified: true,
        registrationInfo: {
          credentialID: Buffer.from('cred123'),
          credentialPublicKey: Buffer.from('pubkey123'),
          counter: 0,
          credentialDeviceType: 'singleDevice',
          credentialBackedUp: false
        }
      });
      
      const result = await webauthnService.verifyRegistration(
        'user123',
        credential,
        'My Security Key'
      );
      
      expect(result.verified).toBe(true);
      expect(result.passkey).toBeDefined();
      expect(result.passkey?.name).toBe('My Security Key');
      expect(result.passkey?.deviceType).toBe('singleDevice');
      
      expect(mockRedisService.hset).toHaveBeenCalled();
      expect(mockRedisService.sadd).toHaveBeenCalled();
    });
    
    it('should fail registration with expired challenge', async () => {
      mockRedisService.getWebAuthnChallenge.mockResolvedValueOnce(null);
      
      const result = await webauthnService.verifyRegistration(
        'user123',
        { id: 'cred123' },
        'My Key'
      );
      
      expect(result.verified).toBe(false);
      expect(result.passkey).toBeUndefined();
    });
    
    it('should fail registration with invalid credential', async () => {
      mockRedisService.getWebAuthnChallenge.mockResolvedValueOnce('stored-challenge');
      
      (simplewebauthn.verifyRegistrationResponse as jest.MockedFunction<typeof simplewebauthn.verifyRegistrationResponse>).mockResolvedValueOnce({
        verified: false
      });
      
      const result = await webauthnService.verifyRegistration(
        'user123',
        { id: 'invalid' }
      );
      
      expect(result.verified).toBe(false);
      expect(mockRedisService.hset).not.toHaveBeenCalled();
    });
  });
  
  describe('Authentication Flow', () => {
    it('should generate authentication options for user', async () => {
      const passkey = {
        id: 'passkey-123',
        userId: 'user123',
        credentialID: 'cred123',
        credentialPublicKey: 'pubkey123',
        counter: 5,
        transports: ['usb'],
        deviceType: 'cross-platform',
        backedUp: false,
        createdAt: new Date()
      };
      
      mockRedisService.smembers.mockResolvedValueOnce(['passkey-123']);
      mockRedisService.hget.mockResolvedValueOnce(passkey);
      
      const mockOptions = {
        challenge: 'auth-challenge',
        rpId: 'localhost',
        allowCredentials: [{
          id: Buffer.from('cred123', 'base64'),
          type: 'public-key',
          transports: ['usb']
        }],
        userVerification: 'preferred',
        timeout: 300000
      };
      
      (simplewebauthn.generateAuthenticationOptions as jest.MockedFunction<typeof simplewebauthn.generateAuthenticationOptions>).mockResolvedValueOnce(mockOptions as any);
      
      const options = await webauthnService.generateAuthenticationOptions('user123');
      
      expect(options.challenge).toBe('auth-challenge');
      expect(options.allowCredentials).toHaveLength(1);
      expect(mockRedisService.storeWebAuthnChallenge).toHaveBeenCalledWith(
        'user123',
        'auth-challenge',
        'authentication',
        300
      );
    });
    
    it('should generate authentication options for passwordless', async () => {
      const mockOptions = {
        challenge: 'auth-challenge',
        rpId: 'localhost',
        allowCredentials: undefined,
        userVerification: 'preferred'
      };
      
      (simplewebauthn.generateAuthenticationOptions as jest.MockedFunction<typeof simplewebauthn.generateAuthenticationOptions>).mockResolvedValueOnce(mockOptions as any);
      
      const options = await webauthnService.generateAuthenticationOptions();
      
      expect(options.allowCredentials).toBeUndefined();
      expect(mockRedisService.storeWebAuthnChallenge).toHaveBeenCalledWith(
        'anonymous',
        'auth-challenge',
        'authentication',
        300
      );
    });
    
    it('should verify authentication and update counter', async () => {
      const credential = {
        id: 'Y3JlZDEyMw', // base64url of 'cred123'
        response: {
          clientDataJSON: 'client-data',
          authenticatorData: 'auth-data',
          signature: 'signature'
        }
      };
      
      const passkey = {
        id: 'passkey-123',
        userId: 'user123',
        credentialID: 'cred123', // base64
        credentialPublicKey: 'pubkey123',
        counter: 5,
        deviceType: 'platform',
        backedUp: false,
        createdAt: new Date()
      };
      
      mockRedisService.getWebAuthnChallenge.mockResolvedValueOnce('stored-challenge');
      mockRedisService.hgetall.mockResolvedValueOnce({ 'passkey-123': passkey });
      
      (simplewebauthn.verifyAuthenticationResponse as jest.Mock).mockResolvedValueOnce({
        verified: true,
        authenticationInfo: {
          newCounter: 6
        }
      });
      
      const result = await webauthnService.verifyAuthentication(credential, 'user123');
      
      expect(result.verified).toBe(true);
      expect(result.userId).toBe('user123');
      expect(result.passkey).toBeDefined();
      expect(result.passkey?.counter).toBe(6);
      expect(result.passkey?.lastUsedAt).toBeDefined();
      
      expect(mockRedisService.hset).toHaveBeenCalled();
    });
    
    it('should fail authentication with expired challenge', async () => {
      mockRedisService.getWebAuthnChallenge.mockResolvedValueOnce(null);
      
      const result = await webauthnService.verifyAuthentication(
        { id: 'cred123' },
        'user123'
      );
      
      expect(result.verified).toBe(false);
      expect(result.userId).toBeUndefined();
    });
    
    it('should fail authentication with unknown passkey', async () => {
      mockRedisService.getWebAuthnChallenge.mockResolvedValueOnce('stored-challenge');
      mockRedisService.hgetall.mockResolvedValueOnce({});
      
      const result = await webauthnService.verifyAuthentication(
        { id: 'unknown' }
      );
      
      expect(result.verified).toBe(false);
    });
    
    it('should fail authentication with invalid signature', async () => {
      const passkey = {
        id: 'passkey-123',
        userId: 'user123',
        credentialID: 'cred123',
        credentialPublicKey: 'pubkey123',
        counter: 5,
        deviceType: 'platform',
        backedUp: false,
        createdAt: new Date()
      };
      
      mockRedisService.getWebAuthnChallenge.mockResolvedValueOnce('stored-challenge');
      mockRedisService.hgetall.mockResolvedValueOnce({ 'passkey-123': passkey });
      
      (simplewebauthn.verifyAuthenticationResponse as jest.Mock).mockResolvedValueOnce({
        verified: false
      });
      
      const result = await webauthnService.verifyAuthentication(
        { id: 'Y3JlZDEyMw' }
      );
      
      expect(result.verified).toBe(false);
      expect(mockRedisService.hset).not.toHaveBeenCalled();
    });
  });
  
  describe('Passkey Management', () => {
    it('should get user passkeys', async () => {
      const passkey1 = {
        id: 'passkey-1',
        userId: 'user123',
        credentialID: 'cred1',
        credentialPublicKey: 'pubkey1',
        counter: 0,
        name: 'Key 1',
        deviceType: 'platform',
        backedUp: true,
        createdAt: new Date()
      };
      
      const passkey2 = {
        id: 'passkey-2',
        userId: 'user123',
        credentialID: 'cred2',
        credentialPublicKey: 'pubkey2',
        counter: 10,
        name: 'Key 2',
        deviceType: 'cross-platform',
        backedUp: false,
        createdAt: new Date()
      };
      
      mockRedisService.smembers.mockResolvedValueOnce(['passkey-1', 'passkey-2']);
      mockRedisService.hget
        .mockResolvedValueOnce(passkey1)
        .mockResolvedValueOnce(passkey2);
      
      const passkeys = await webauthnService.getUserPasskeys('user123');
      
      expect(passkeys).toHaveLength(2);
      expect(passkeys[0].name).toBe('Key 1');
      expect(passkeys[1].name).toBe('Key 2');
    });
    
    it('should delete passkey', async () => {
      const passkey = {
        id: 'passkey-123',
        userId: 'user123',
        credentialID: 'cred123',
        credentialPublicKey: 'pubkey123',
        counter: 0,
        deviceType: 'platform',
        backedUp: false,
        createdAt: new Date()
      };
      
      mockRedisService.hget.mockResolvedValueOnce(passkey);
      mockRedisService.hdel.mockResolvedValueOnce(1);
      mockRedisService.srem.mockResolvedValueOnce(1);
      
      const result = await webauthnService.deletePasskey('passkey-123');
      
      expect(result).toBe(true);
      expect(mockRedisService.hdel).toHaveBeenCalledWith('passkeys', 'passkey-123');
      expect(mockRedisService.srem).toHaveBeenCalledWith(
        'user:passkeys:user123',
        'passkey-123'
      );
    });
    
    it('should update passkey name', async () => {
      const passkey = {
        id: 'passkey-123',
        userId: 'user123',
        credentialID: 'cred123',
        credentialPublicKey: 'pubkey123',
        counter: 0,
        name: 'Old Name',
        deviceType: 'platform',
        backedUp: false,
        createdAt: new Date()
      };
      
      mockRedisService.hget.mockResolvedValueOnce(passkey);
      mockRedisService.hset.mockResolvedValueOnce(1);
      
      const result = await webauthnService.updatePasskeyName('passkey-123', 'New Name');
      
      expect(result).toBe(true);
      expect(mockRedisService.hset).toHaveBeenCalledWith(
        'passkeys',
        'passkey-123',
        expect.objectContaining({ name: 'New Name' })
      );
    });
    
    it('should return false when updating non-existent passkey', async () => {
      mockRedisService.hget.mockResolvedValueOnce(null);
      
      const result = await webauthnService.updatePasskeyName('non-existent', 'New Name');
      
      expect(result).toBe(false);
      expect(mockRedisService.hset).not.toHaveBeenCalled();
    });
  });
  
  describe('Statistics', () => {
    it('should calculate passkey statistics', async () => {
      const passkey1 = {
        id: 'passkey-1',
        userId: 'user1',
        credentialID: 'cred1',
        credentialPublicKey: 'pubkey1',
        counter: 0,
        deviceType: 'platform',
        backedUp: true,
        createdAt: new Date()
      };
      
      const passkey2 = {
        id: 'passkey-2',
        userId: 'user2',
        credentialID: 'cred2',
        credentialPublicKey: 'pubkey2',
        counter: 0,
        deviceType: 'platform',
        backedUp: false,
        createdAt: new Date()
      };
      
      const passkey3 = {
        id: 'passkey-3',
        userId: 'user1',
        credentialID: 'cred3',
        credentialPublicKey: 'pubkey3',
        counter: 0,
        deviceType: 'cross-platform',
        backedUp: true,
        createdAt: new Date()
      };
      
      // Mock internal state
      (webauthnService as any).passkeys.set('passkey-1', passkey1);
      (webauthnService as any).passkeys.set('passkey-2', passkey2);
      (webauthnService as any).passkeys.set('passkey-3', passkey3);
      (webauthnService as any).userPasskeys.set('user1', new Set(['passkey-1', 'passkey-3']));
      (webauthnService as any).userPasskeys.set('user2', new Set(['passkey-2']));
      
      const stats = await webauthnService.getStats();
      
      expect(stats.totalPasskeys).toBe(3);
      expect(stats.userCount).toBe(2);
      expect(stats.deviceTypes.platform).toBe(2);
      expect(stats.deviceTypes['cross-platform']).toBe(1);
      expect(stats.backedUpCount).toBe(2);
    });
  });
  
  describe('Challenge Cleanup', () => {
    it('should set TTL for challenges without expiry', async () => {
      mockRedisService.keys.mockResolvedValueOnce([
        'webauthn:registration:user1',
        'webauthn:authentication:user2'
      ]);
      mockRedisService.ttl
        .mockResolvedValueOnce(-1) // No TTL
        .mockResolvedValueOnce(100); // Has TTL
      mockRedisService.expire.mockResolvedValueOnce(true);
      
      await webauthnService.cleanupExpiredChallenges();
      
      expect(mockRedisService.expire).toHaveBeenCalledWith(
        'webauthn:registration:user1',
        300
      );
      expect(mockRedisService.expire).toHaveBeenCalledTimes(1);
    });
  });
});