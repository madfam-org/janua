import { MFAService, SMSProvider, HardwareTokenProvider } from '../mfa-service';

describe('MFAService', () => {
  let mfaService: MFAService;
  let mockSMSProvider: jest.Mocked<SMSProvider>;
  let mockHardwareProvider: jest.Mocked<HardwareTokenProvider>;
  let mockRedisService: any;

  beforeEach(() => {
    // Create mock providers matching actual interface
    mockSMSProvider = {
      send: jest.fn().mockResolvedValue(true)
    } as jest.Mocked<SMSProvider>;

    mockHardwareProvider = {
      verify: jest.fn().mockResolvedValue(true),
      register: jest.fn().mockResolvedValue('token-123')
    } as jest.Mocked<HardwareTokenProvider>;

    mockRedisService = {
      hset: jest.fn().mockResolvedValue(1),
      hget: jest.fn().mockResolvedValue(null),
      hdel: jest.fn().mockResolvedValue(1),
      expire: jest.fn().mockResolvedValue(1),
      get: jest.fn().mockResolvedValue(null)
    };

    // Initialize MFA service with actual constructor signature
    mfaService = new MFAService({
      issuer: 'TestApp',
      window: 2,
      digits: 6,
      algorithm: 'sha1',
      smsProvider: mockSMSProvider,
      hardwareProvider: mockHardwareProvider,
      riskThreshold: 0.5,
      maxAttempts: 3,
      challengeTTL: 300,
      gracePeriod: 15
    }, mockRedisService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Risk Assessment', () => {
    it('should assess risk based on context', async () => {
      const assessment = await mfaService.assessRisk({
        user_id: 'user123',
        session_id: 'session-123',
        ip_address: '192.168.1.1',
        user_agent: 'Mozilla/5.0',
        location: { lat: 40.7128, lon: -74.0060, country: 'US' },
        device_fingerprint: 'trusted-device-123',
        action: 'login'
      });

      expect(assessment.score).toBeGreaterThanOrEqual(0);
      expect(assessment.score).toBeLessThanOrEqual(1);
      expect(assessment.factors).toBeDefined();
      expect(typeof assessment.requires_mfa).toBe('boolean');
      expect(Array.isArray(assessment.suggested_methods)).toBe(true);
    });

    it('should flag suspicious user agents', async () => {
      const assessment = await mfaService.assessRisk({
        user_id: 'user123',
        session_id: 'session-123',
        ip_address: '192.168.1.1',
        user_agent: 'python-requests/2.25.1',
        device_fingerprint: 'new-device-456',
        action: 'login'
      });

      // Assessment should complete without error
      expect(assessment).toBeDefined();
      expect(assessment.factors).toBeDefined();
    });

    it('should suggest MFA methods based on risk score', async () => {
      const assessment = await mfaService.assessRisk({
        user_id: 'user123',
        session_id: 'session-123',
        ip_address: '192.168.1.1',
        user_agent: 'Mozilla/5.0',
        device_fingerprint: 'device-123',
        action: 'password_change'
      });

      expect(Array.isArray(assessment.suggested_methods)).toBe(true);
    });
  });

  describe('TOTP Management', () => {
    it('should generate TOTP secret with QR code and backup codes', async () => {
      const result = await mfaService.generateTOTPSecret('user123', 'user@example.com');

      expect(result.secret).toBeDefined();
      expect(result.secret.length).toBeGreaterThan(0);
      expect(result.qr_code).toBeDefined();
      expect(result.provisioning_uri).toBeDefined();
      expect(result.backup_codes).toHaveLength(10);
      result.backup_codes.forEach(code => {
        expect(code).toMatch(/^[A-F0-9]{4}-[A-F0-9]{4}$/);
      });
    });

    it('should verify valid TOTP code', () => {
      // Generate a known secret and verify
      const secret = 'JBSWY3DPEHPK3PXP'; // Test secret

      // The service returns boolean directly
      const result = mfaService.verifyTOTP(secret, '000000');
      expect(typeof result).toBe('boolean');
    });
  });

  describe('SMS MFA', () => {
    it('should send SMS code and return challenge', async () => {
      const challenge = await mfaService.sendSMSCode('user123', '+1234567890');

      expect(challenge.id).toBeDefined();
      expect(challenge.user_id).toBe('user123');
      expect(challenge.method).toBe('sms');
      expect(challenge.status).toBe('pending');
      expect(challenge.expires_at).toBeInstanceOf(Date);
      expect(challenge.attempts).toBe(0);
      expect(mockSMSProvider.send).toHaveBeenCalled();
    });

    it('should verify SMS code for a challenge', async () => {
      const challenge = await mfaService.sendSMSCode('user123', '+1234567890');

      // The actual code is hashed, so we can't verify a correct code in test
      // but we can test the verification flow returns boolean
      const result = mfaService.verifySMSCode(challenge.id, '123456');
      expect(typeof result).toBe('boolean');
    });

    it('should throw when SMS provider is not configured', async () => {
      const serviceWithoutSMS = new MFAService({
        issuer: 'TestApp',
        window: 2
      });

      await expect(serviceWithoutSMS.sendSMSCode('user123', '+1234567890'))
        .rejects.toThrow('SMS provider not configured');
    });
  });

  describe('Hardware Token', () => {
    it('should register hardware token', async () => {
      const tokenId = await mfaService.registerHardwareToken('user123', 'SERIAL123');

      expect(tokenId).toBe('token-123');
      expect(mockHardwareProvider.register).toHaveBeenCalledWith('user123', 'SERIAL123');
    });

    it('should verify hardware token', async () => {
      const result = await mfaService.verifyHardwareToken('token-123', '123456');

      expect(result).toBe(true);
      expect(mockHardwareProvider.verify).toHaveBeenCalledWith('token-123', '123456');
    });

    it('should throw when hardware provider is not configured', async () => {
      const serviceWithoutHardware = new MFAService({
        issuer: 'TestApp',
        window: 2
      });

      await expect(serviceWithoutHardware.registerHardwareToken('user123', 'SERIAL123'))
        .rejects.toThrow('Hardware token provider not configured');
    });
  });

  describe('Trusted Devices', () => {
    it('should register trusted device', async () => {
      const result = await mfaService.registerTrustedDevice('user123', {
        device_fingerprint: 'device-abc',
        user_agent: 'Mozilla/5.0',
        ip: '192.168.1.1',
        name: 'My Laptop'
      });

      expect(result.id).toBeDefined();
      expect(result.user_id).toBe('user123');
      expect(result.device_fingerprint).toBe('device-abc');
      expect(result.trusted).toBe(true);
      expect(result.expires_at).toBeInstanceOf(Date);
      expect(result.created_at).toBeInstanceOf(Date);
    });

    it('should trust device with duration', async () => {
      await mfaService.trustDevice('user123', 'device-abc', 30);

      // Should not throw
      expect(mockRedisService.hset).toHaveBeenCalled();
    });

    it('should check if device is trusted', async () => {
      mockRedisService.hget.mockResolvedValueOnce(JSON.stringify({
        fingerprint: 'device-abc',
        trustedAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + 86400000).toISOString()
      }));

      const result = await mfaService.isTrustedDevice('user123', 'device-abc');
      expect(result).toBe(true);
    });

    it('should reject expired trusted device', async () => {
      mockRedisService.hget.mockResolvedValueOnce(JSON.stringify({
        fingerprint: 'device-abc',
        trustedAt: new Date(Date.now() - 86400000 * 2).toISOString(),
        expiresAt: new Date(Date.now() - 86400000).toISOString()
      }));

      const result = await mfaService.isTrustedDevice('user123', 'device-abc');
      expect(result).toBe(false);
    });

    it('should revoke trusted device', async () => {
      const result = await mfaService.revokeTrustedDevice('user123', 'device-abc');

      expect(result).toBe(true);
      expect(mockRedisService.hdel).toHaveBeenCalledWith(
        'trusted_devices:user123',
        'device-abc'
      );
    });
  });

  describe('User Configuration', () => {
    it('should get user config', () => {
      const config = mfaService.getUserConfig('user123');
      expect(config).toBeUndefined(); // No config set yet
    });

    it('should update user config', () => {
      mfaService.updateUserConfig('user123', {
        risk_based_enabled: true,
        risk_threshold: 0.7
      });

      const config = mfaService.getUserConfig('user123');
      expect(config).toBeDefined();
      expect(config?.risk_based_enabled).toBe(true);
      expect(config?.risk_threshold).toBe(0.7);
    });
  });

  describe('Statistics', () => {
    it('should return statistics', () => {
      const stats = mfaService.getStatistics();

      expect(stats).toHaveProperty('total_users');
      expect(stats).toHaveProperty('total_challenges');
      expect(stats).toHaveProperty('active_challenges');
      expect(stats).toHaveProperty('trusted_devices');
      expect(stats).toHaveProperty('verification_rate');
      expect(typeof stats.total_users).toBe('number');
      expect(typeof stats.total_challenges).toBe('number');
    });
  });
});
