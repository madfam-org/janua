import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { MFAService } from '../mfa-service';
import { SMSService } from '../sms-provider.service';
import { HardwareTokenService } from '../hardware-token-provider.service';
import { RedisService } from '../redis.service';

// Mock dependencies
jest.mock('../sms-provider.service');
jest.mock('../hardware-token-provider.service');
jest.mock('../redis.service');

describe('MFAService', () => {
  let mfaService: MFAService;
  let mockSMSService: jest.Mocked<SMSService>;
  let mockHardwareTokenService: jest.Mocked<HardwareTokenService>;
  let mockRedisService: jest.Mocked<RedisService>;
  
  beforeEach(() => {
    // Create mock instances
    mockSMSService = new SMSService({ provider: 'mock' }) as jest.Mocked<SMSService>;
    mockHardwareTokenService = new HardwareTokenService() as jest.Mocked<HardwareTokenService>;
    mockRedisService = new RedisService({ host: 'localhost', port: 6379 }) as jest.Mocked<RedisService>;
    
    // Initialize MFA service
    mfaService = new MFAService({
      smsService: mockSMSService,
      hardwareTokenService: mockHardwareTokenService,
      redisService: mockRedisService,
      riskThresholds: {
        low: 30,
        medium: 60,
        high: 80
      }
    });
  });
  
  afterEach(() => {
    jest.clearAllMocks();
  });
  
  describe('Risk Assessment', () => {
    it('should assess low risk for trusted device and location', async () => {
      const assessment = await mfaService.assessRisk({
        user_id: 'user123',
        ip: '192.168.1.1',
        user_agent: 'Mozilla/5.0',
        location: { country: 'US', city: 'New York' },
        device_fingerprint: 'trusted-device-123',
        session_metadata: {
          trusted_device: true,
          last_successful_auth: new Date(Date.now() - 3600000) // 1 hour ago
        }
      });
      
      expect(assessment.riskScore).toBeLessThan(30);
      expect(assessment.riskLevel).toBe('low');
      expect(assessment.factors).toContain('trusted_device');
    });
    
    it('should assess high risk for new location and device', async () => {
      const assessment = await mfaService.assessRisk({
        user_id: 'user123',
        ip: '45.67.89.10',
        user_agent: 'Mozilla/5.0',
        location: { country: 'CN', city: 'Beijing' },
        device_fingerprint: 'new-device-456',
        session_metadata: {
          trusted_device: false,
          first_seen: new Date()
        }
      });
      
      expect(assessment.riskScore).toBeGreaterThan(60);
      expect(assessment.riskLevel).toBe('high');
      expect(assessment.factors).toContain('new_device');
      expect(assessment.factors).toContain('new_location');
    });
    
    it('should detect impossible travel', async () => {
      // Mock previous location
      mockRedisService.get.mockResolvedValueOnce({
        location: { country: 'US', city: 'New York' },
        timestamp: Date.now() - 1800000 // 30 minutes ago
      });
      
      const assessment = await mfaService.assessRisk({
        user_id: 'user123',
        ip: '45.67.89.10',
        user_agent: 'Mozilla/5.0',
        location: { country: 'JP', city: 'Tokyo' },
        device_fingerprint: 'device-123',
        session_metadata: {}
      });
      
      expect(assessment.riskScore).toBeGreaterThan(80);
      expect(assessment.riskLevel).toBe('critical');
      expect(assessment.factors).toContain('impossible_travel');
    });
    
    it('should suggest appropriate MFA methods based on risk', async () => {
      const lowRiskAssessment = await mfaService.assessRisk({
        user_id: 'user123',
        ip: '192.168.1.1',
        user_agent: 'Mozilla/5.0',
        location: { country: 'US', city: 'New York' },
        device_fingerprint: 'trusted-device-123',
        session_metadata: { trusted_device: true }
      });
      
      expect(lowRiskAssessment.suggestedMFAMethods).toEqual([]);
      
      const highRiskAssessment = await mfaService.assessRisk({
        user_id: 'user123',
        ip: '45.67.89.10',
        user_agent: 'Mozilla/5.0',
        location: { country: 'CN', city: 'Beijing' },
        device_fingerprint: 'new-device-456',
        session_metadata: {}
      });
      
      expect(highRiskAssessment.suggestedMFAMethods).toContain('hardware_token');
      expect(highRiskAssessment.suggestedMFAMethods).toContain('totp');
    });
  });
  
  describe('TOTP Management', () => {
    it('should generate TOTP secret', async () => {
      const result = await mfaService.generateTOTPSecret('user123');
      
      expect(result.secret).toBeDefined();
      expect(result.qr_code).toContain('otpauth://totp');
      expect(result.backup_codes).toHaveLength(10);
      result.backup_codes.forEach(code => {
        expect(code).toMatch(/^[A-Z0-9]{8}$/);
      });
    });
    
    it('should verify valid TOTP code', async () => {
      const { secret } = await mfaService.generateTOTPSecret('user123');
      
      // Mock TOTP verification
      const mockCode = '123456';
      jest.spyOn(mfaService as any, 'verifyTOTPCode').mockResolvedValueOnce(true);
      
      const result = await mfaService.verifyTOTP('user123', mockCode, secret);
      
      expect(result.valid).toBe(true);
      expect(result.method).toBe('totp');
    });
    
    it('should reject invalid TOTP code', async () => {
      const { secret } = await mfaService.generateTOTPSecret('user123');
      
      jest.spyOn(mfaService as any, 'verifyTOTPCode').mockResolvedValueOnce(false);
      
      const result = await mfaService.verifyTOTP('user123', '000000', secret);
      
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Invalid TOTP code');
    });
  });
  
  describe('SMS MFA', () => {
    it('should send SMS code', async () => {
      mockSMSService.sendVerificationCode.mockResolvedValueOnce({
        success: true,
        messageId: 'msg-123',
        status: 'sent'
      });
      
      mockRedisService.storeMFACode = jest.fn().mockResolvedValueOnce(undefined);
      
      const result = await mfaService.sendSMSCode('user123', '+1234567890');
      
      expect(result.id).toBeDefined();
      expect(result.type).toBe('sms');
      expect(result.status).toBe('pending');
      expect(result.expires_at).toBeDefined();
      expect(mockSMSService.sendVerificationCode).toHaveBeenCalled();
    });
    
    it('should verify SMS code', async () => {
      mockRedisService.verifyMFACode.mockResolvedValueOnce(true);
      
      const result = await mfaService.verifySMSCode('user123', '123456');
      
      expect(result.valid).toBe(true);
      expect(result.method).toBe('sms');
      expect(mockRedisService.verifyMFACode).toHaveBeenCalledWith(
        'user123',
        '123456',
        'sms',
        3
      );
    });
    
    it('should handle SMS sending failure', async () => {
      mockSMSService.sendVerificationCode.mockResolvedValueOnce({
        success: false,
        error: 'Network error'
      });
      
      await expect(mfaService.sendSMSCode('user123', '+1234567890'))
        .rejects.toThrow('Failed to send SMS code');
    });
  });
  
  describe('Hardware Token', () => {
    it('should register hardware token', async () => {
      const mockToken = {
        id: 'token-123',
        type: 'yubikey' as const,
        name: 'YubiKey 5',
        algorithm: 'ECC' as const,
        registeredAt: new Date()
      };
      
      mockHardwareTokenService.registerToken.mockResolvedValueOnce(mockToken);
      
      const result = await mfaService.registerHardwareToken('user123', 'yubikey');
      
      expect(result.id).toBe('token-123');
      expect(result.type).toBe('hardware_token');
      expect(result.metadata.token_type).toBe('yubikey');
    });
    
    it('should verify hardware token', async () => {
      mockHardwareTokenService.verifyToken.mockResolvedValueOnce({
        success: true,
        tokenId: 'token-123'
      });
      
      const result = await mfaService.verifyHardwareToken(
        'token-123',
        'challenge-abc',
        'response-xyz'
      );
      
      expect(result.valid).toBe(true);
      expect(result.method).toBe('hardware_token');
    });
  });
  
  describe('Adaptive MFA', () => {
    it('should skip MFA for low risk with bypass enabled', async () => {
      const assessment = await mfaService.assessRisk({
        user_id: 'user123',
        ip: '192.168.1.1',
        user_agent: 'Mozilla/5.0',
        location: { country: 'US', city: 'New York' },
        device_fingerprint: 'trusted-device-123',
        session_metadata: { trusted_device: true }
      });
      
      const shouldRequireMFA = mfaService.shouldRequireMFA(assessment, {
        bypassForLowRisk: true
      });
      
      expect(shouldRequireMFA).toBe(false);
    });
    
    it('should require MFA for medium risk', async () => {
      const assessment = await mfaService.assessRisk({
        user_id: 'user123',
        ip: '192.168.1.1',
        user_agent: 'NewBrowser/1.0',
        location: { country: 'US', city: 'Chicago' },
        device_fingerprint: 'semi-trusted-device',
        session_metadata: {}
      });
      
      const shouldRequireMFA = mfaService.shouldRequireMFA(assessment, {
        bypassForLowRisk: true
      });
      
      expect(shouldRequireMFA).toBe(true);
    });
    
    it('should enforce strong MFA for high risk', async () => {
      const assessment = await mfaService.assessRisk({
        user_id: 'user123',
        ip: '45.67.89.10',
        user_agent: 'Mozilla/5.0',
        location: { country: 'RU', city: 'Moscow' },
        device_fingerprint: 'suspicious-device',
        session_metadata: {}
      });
      
      const mfaRequirements = mfaService.getAdaptiveMFARequirements(assessment);
      
      expect(mfaRequirements.required).toBe(true);
      expect(mfaRequirements.allowedMethods).not.toContain('sms');
      expect(mfaRequirements.minimumFactors).toBeGreaterThanOrEqual(2);
    });
  });
  
  describe('Backup Codes', () => {
    it('should generate backup codes', () => {
      const codes = mfaService.generateBackupCodes(10);
      
      expect(codes).toHaveLength(10);
      codes.forEach(code => {
        expect(code).toMatch(/^[A-Z0-9]{8}$/);
      });
      
      // Ensure codes are unique
      const uniqueCodes = new Set(codes);
      expect(uniqueCodes.size).toBe(10);
    });
    
    it('should verify backup code', async () => {
      const codes = mfaService.generateBackupCodes(5);
      
      // Mock storing codes
      mockRedisService.hset.mockResolvedValueOnce(1);
      mockRedisService.hget.mockResolvedValueOnce({
        codes: codes.map(code => ({ code, used: false }))
      });
      
      await mfaService.storeBackupCodes('user123', codes);
      
      const result = await mfaService.verifyBackupCode('user123', codes[0]);
      
      expect(result.valid).toBe(true);
      expect(result.remaining).toBe(4);
    });
    
    it('should not allow reuse of backup code', async () => {
      const codes = mfaService.generateBackupCodes(5);
      
      mockRedisService.hget.mockResolvedValueOnce({
        codes: codes.map(code => ({ 
          code, 
          used: code === codes[0] 
        }))
      });
      
      const result = await mfaService.verifyBackupCode('user123', codes[0]);
      
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Backup code already used');
    });
  });
  
  describe('MFA Challenge Management', () => {
    it('should create MFA challenge', async () => {
      const challenge = await mfaService.createMFAChallenge('user123', ['totp', 'sms']);
      
      expect(challenge.id).toBeDefined();
      expect(challenge.user_id).toBe('user123');
      expect(challenge.available_methods).toEqual(['totp', 'sms']);
      expect(challenge.status).toBe('pending');
      expect(challenge.expires_at).toBeDefined();
    });
    
    it('should complete MFA challenge with valid verification', async () => {
      const challenge = await mfaService.createMFAChallenge('user123', ['totp']);
      
      jest.spyOn(mfaService, 'verifyTOTP').mockResolvedValueOnce({
        valid: true,
        method: 'totp'
      });
      
      const result = await mfaService.completeMFAChallenge(challenge.id, {
        method: 'totp',
        code: '123456'
      });
      
      expect(result.success).toBe(true);
      expect(result.challenge.status).toBe('completed');
    });
    
    it('should fail MFA challenge with invalid verification', async () => {
      const challenge = await mfaService.createMFAChallenge('user123', ['totp']);
      
      jest.spyOn(mfaService, 'verifyTOTP').mockResolvedValueOnce({
        valid: false,
        method: 'totp',
        error: 'Invalid code'
      });
      
      const result = await mfaService.completeMFAChallenge(challenge.id, {
        method: 'totp',
        code: '000000'
      });
      
      expect(result.success).toBe(false);
      expect(result.error).toBe('Invalid code');
      expect(result.challenge.attempts).toBe(1);
    });
    
    it('should lock challenge after max attempts', async () => {
      const challenge = await mfaService.createMFAChallenge('user123', ['totp']);
      
      jest.spyOn(mfaService, 'verifyTOTP').mockResolvedValue({
        valid: false,
        method: 'totp',
        error: 'Invalid code'
      });
      
      // Attempt 3 times (max attempts)
      for (let i = 0; i < 3; i++) {
        await mfaService.completeMFAChallenge(challenge.id, {
          method: 'totp',
          code: '000000'
        });
      }
      
      const finalResult = await mfaService.completeMFAChallenge(challenge.id, {
        method: 'totp',
        code: '123456'
      });
      
      expect(finalResult.success).toBe(false);
      expect(finalResult.error).toBe('Challenge locked due to too many attempts');
      expect(finalResult.challenge.status).toBe('locked');
    });
  });
  
  describe('Trusted Devices', () => {
    it('should register trusted device', async () => {
      mockRedisService.hset.mockResolvedValueOnce(1);
      
      const result = await mfaService.registerTrustedDevice('user123', {
        device_fingerprint: 'device-abc',
        user_agent: 'Mozilla/5.0',
        ip: '192.168.1.1',
        name: 'My Laptop'
      });
      
      expect(result.id).toBeDefined();
      expect(result.user_id).toBe('user123');
      expect(result.trusted).toBe(true);
      expect(result.expires_at).toBeDefined();
    });
    
    it('should verify trusted device', async () => {
      const device = {
        id: 'device-123',
        user_id: 'user123',
        device_fingerprint: 'device-abc',
        trusted: true,
        expires_at: new Date(Date.now() + 86400000) // 1 day from now
      };
      
      mockRedisService.hget.mockResolvedValueOnce(device);
      
      const result = await mfaService.isTrustedDevice('user123', 'device-abc');
      
      expect(result).toBe(true);
    });
    
    it('should reject expired trusted device', async () => {
      const device = {
        id: 'device-123',
        user_id: 'user123',
        device_fingerprint: 'device-abc',
        trusted: true,
        expires_at: new Date(Date.now() - 86400000) // 1 day ago
      };
      
      mockRedisService.hget.mockResolvedValueOnce(device);
      
      const result = await mfaService.isTrustedDevice('user123', 'device-abc');
      
      expect(result).toBe(false);
    });
    
    it('should revoke trusted device', async () => {
      mockRedisService.hdel.mockResolvedValueOnce(1);
      
      const result = await mfaService.revokeTrustedDevice('user123', 'device-123');
      
      expect(result).toBe(true);
      expect(mockRedisService.hdel).toHaveBeenCalledWith(
        'trusted_devices:user123',
        'device-123'
      );
    });
  });
});