import { EventEmitter } from 'events';
import * as crypto from 'crypto';
import { createLogger } from '../utils/logger';

const logger = createLogger('HardwareToken');

// Hardware Token Types
type TokenType = 'yubikey' | 'fido2' | 'rsa-securid' | 'google-titan' | 'solo-key' | 'mock';

interface HardwareToken {
  id: string;
  type: TokenType;
  name: string;
  serial?: string;
  publicKey?: string;
  algorithm: 'RSA' | 'ECC' | 'HMAC' | 'FIDO2';
  registeredAt: Date;
  lastUsedAt?: Date;
  metadata?: Record<string, any>;
}

interface TokenVerificationResult {
  success: boolean;
  tokenId?: string;
  error?: string;
  metadata?: Record<string, any>;
}

interface HardwareTokenProvider {
  name: string;
  type: TokenType;
  register(userId: string, challenge?: string): Promise<HardwareToken>;
  verify(tokenId: string, challenge: string, response: any): Promise<TokenVerificationResult>;
  getInfo(tokenId: string): Promise<HardwareToken | null>;
}

// YubiKey Provider
class YubiKeyProvider implements HardwareTokenProvider {
  name = 'YubiKey';
  type: TokenType = 'yubikey';

  async register(_userId: string, _challenge?: string): Promise<HardwareToken> {
    // In production, this would integrate with Yubico API
    const token: HardwareToken = {
      id: `yubikey-${crypto.randomBytes(16).toString('hex')}`,
      type: 'yubikey',
      name: 'YubiKey 5 NFC',
      serial: crypto.randomBytes(8).toString('hex').toUpperCase(),
      publicKey: crypto.randomBytes(32).toString('base64'),
      algorithm: 'ECC',
      registeredAt: new Date(),
      metadata: {
        firmware: '5.4.3',
        capabilities: ['OTP', 'FIDO2', 'PIV', 'OpenPGP']
      }
    };
    
    return token;
  }
  
  async verify(tokenId: string, challenge: string, response: any): Promise<TokenVerificationResult> {
    try {
      // In production, verify with Yubico OTP validation service
      // For now, simulate verification
      
      // Validate OTP format (44 characters for YubiKey OTP)
      if (typeof response !== 'string' || response.length !== 44) {
        return {
          success: false,
          error: 'Invalid YubiKey OTP format'
        };
      }
      
      // Extract components
      const publicId = response.substring(0, 12);
      const otp = response.substring(12);
      
      // Simulate API call to Yubico
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // In production, check against Yubico servers
      const isValid = otp.length === 32; // Simplified check
      
      if (isValid) {
        return {
          success: true,
          tokenId,
          metadata: {
            publicId,
            timestamp: Date.now()
          }
        };
      }
      
      return {
        success: false,
        error: 'Invalid OTP'
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  async getInfo(tokenId: string): Promise<HardwareToken | null> {
    // In production, retrieve from database
    return {
      id: tokenId,
      type: 'yubikey',
      name: 'YubiKey 5 NFC',
      algorithm: 'ECC',
      registeredAt: new Date()
    };
  }
}

// FIDO2 Provider (for hardware security keys)
class FIDO2Provider implements HardwareTokenProvider {
  name = 'FIDO2';
  type: TokenType = 'fido2';
  
  async register(userId: string, challenge?: string): Promise<HardwareToken> {
    // This would integrate with WebAuthn for FIDO2 keys
    const token: HardwareToken = {
      id: `fido2-${crypto.randomBytes(16).toString('hex')}`,
      type: 'fido2',
      name: 'Security Key',
      publicKey: crypto.randomBytes(65).toString('base64'), // P-256 public key
      algorithm: 'ECC',
      registeredAt: new Date(),
      metadata: {
        aaguid: crypto.randomBytes(16).toString('hex'),
        attestationType: 'packed',
        userVerification: 'preferred'
      }
    };
    
    return token;
  }
  
  async verify(tokenId: string, challenge: string, response: any): Promise<TokenVerificationResult> {
    try {
      // Validate FIDO2 assertion
      if (!response.signature || !response.authenticatorData || !response.clientDataJSON) {
        return {
          success: false,
          error: 'Invalid FIDO2 response format'
        };
      }
      
      // In production, verify signature using public key
      // For now, simulate verification
      const isValid = response.signature && response.signature.length > 0;
      
      if (isValid) {
        return {
          success: true,
          tokenId,
          metadata: {
            signCount: response.signCount || 0
          }
        };
      }
      
      return {
        success: false,
        error: 'Invalid signature'
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  async getInfo(tokenId: string): Promise<HardwareToken | null> {
    return {
      id: tokenId,
      type: 'fido2',
      name: 'Security Key',
      algorithm: 'ECC',
      registeredAt: new Date()
    };
  }
}

// RSA SecurID Provider
class RSASecurIDProvider implements HardwareTokenProvider {
  name = 'RSA SecurID';
  type: TokenType = 'rsa-securid';
  
  async register(userId: string, challenge?: string): Promise<HardwareToken> {
    const token: HardwareToken = {
      id: `securid-${crypto.randomBytes(16).toString('hex')}`,
      type: 'rsa-securid',
      name: 'RSA SecurID Token',
      serial: crypto.randomBytes(6).toString('hex').toUpperCase(),
      algorithm: 'HMAC',
      registeredAt: new Date(),
      metadata: {
        tokenCode: crypto.randomBytes(4).toString('hex'),
        interval: 60 // seconds
      }
    };
    
    return token;
  }
  
  async verify(tokenId: string, challenge: string, response: any): Promise<TokenVerificationResult> {
    try {
      // Validate token code format (6-8 digits for SecurID)
      if (typeof response !== 'string' || !/^\d{6,8}$/.test(response)) {
        return {
          success: false,
          error: 'Invalid SecurID token code format'
        };
      }
      
      // In production, verify with RSA Authentication Manager
      // For now, simulate time-based token verification
      const currentTime = Math.floor(Date.now() / 60000); // minute-based
      const expectedCode = crypto
        .createHash('sha256')
        .update(`${tokenId}-${currentTime}`)
        .digest('hex')
        .substring(0, 6);
      
      // For demo, accept any 6-digit code
      const isValid = response.length === 6;
      
      if (isValid) {
        return {
          success: true,
          tokenId
        };
      }
      
      return {
        success: false,
        error: 'Invalid token code'
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  async getInfo(tokenId: string): Promise<HardwareToken | null> {
    return {
      id: tokenId,
      type: 'rsa-securid',
      name: 'RSA SecurID Token',
      algorithm: 'HMAC',
      registeredAt: new Date()
    };
  }
}

// Mock Provider for Testing
class MockHardwareTokenProvider implements HardwareTokenProvider {
  name = 'Mock Token';
  type: TokenType = 'mock';
  private tokens: Map<string, HardwareToken> = new Map();
  private validCodes: Map<string, string> = new Map();
  
  async register(userId: string, challenge?: string): Promise<HardwareToken> {
    const token: HardwareToken = {
      id: `mock-${crypto.randomBytes(8).toString('hex')}`,
      type: 'mock',
      name: 'Mock Hardware Token',
      serial: 'MOCK-' + crypto.randomBytes(4).toString('hex').toUpperCase(),
      algorithm: 'HMAC',
      registeredAt: new Date(),
      metadata: {
        userId,
        testMode: true
      }
    };
    
    this.tokens.set(token.id, token);
    
    // Generate a valid code for testing
    const validCode = Math.floor(100000 + Math.random() * 900000).toString();
    this.validCodes.set(token.id, validCode);
    
    logger.debug(`Mock Hardware Token Registered: ${token.id}, Valid code: ${validCode}`);
    
    return token;
  }
  
  async verify(tokenId: string, challenge: string, response: any): Promise<TokenVerificationResult> {
    const validCode = this.validCodes.get(tokenId);
    
    if (!validCode) {
      return {
        success: false,
        error: 'Token not found'
      };
    }
    
    if (response === validCode || response === '123456') { // Allow test code
      const token = this.tokens.get(tokenId);
      if (token) {
        token.lastUsedAt = new Date();
      }
      
      return {
        success: true,
        tokenId
      };
    }
    
    return {
      success: false,
      error: 'Invalid code'
    };
  }
  
  async getInfo(tokenId: string): Promise<HardwareToken | null> {
    return this.tokens.get(tokenId) || null;
  }
  
  getValidCode(tokenId: string): string | undefined {
    return this.validCodes.get(tokenId);
  }
}

// Main Hardware Token Service
export class HardwareTokenService extends EventEmitter {
  private providers: Map<TokenType, HardwareTokenProvider> = new Map();
  private registeredTokens: Map<string, HardwareToken> = new Map();
  private userTokens: Map<string, Set<string>> = new Map();
  
  constructor() {
    super();
    
    // Initialize providers
    this.providers.set('yubikey', new YubiKeyProvider());
    this.providers.set('fido2', new FIDO2Provider());
    this.providers.set('rsa-securid', new RSASecurIDProvider());
    this.providers.set('mock', new MockHardwareTokenProvider());
  }
  
  async registerToken(
    userId: string,
    tokenType: TokenType,
    challenge?: string
  ): Promise<HardwareToken> {
    const provider = this.providers.get(tokenType);
    
    if (!provider) {
      throw new Error(`Unsupported token type: ${tokenType}`);
    }
    
    // Register with provider
    const token = await provider.register(userId, challenge);
    
    // Store registration
    this.registeredTokens.set(token.id, token);
    
    // Associate with user
    if (!this.userTokens.has(userId)) {
      this.userTokens.set(userId, new Set());
    }
    this.userTokens.get(userId)!.add(token.id);
    
    // Emit event
    this.emit('token_registered', {
      userId,
      tokenId: token.id,
      tokenType,
      timestamp: new Date()
    });
    
    return token;
  }
  
  async verifyToken(
    tokenId: string,
    challenge: string,
    response: any
  ): Promise<TokenVerificationResult> {
    const token = this.registeredTokens.get(tokenId);
    
    if (!token) {
      return {
        success: false,
        error: 'Token not registered'
      };
    }
    
    const provider = this.providers.get(token.type);
    
    if (!provider) {
      return {
        success: false,
        error: 'Provider not found'
      };
    }
    
    // Verify with provider
    const result = await provider.verify(tokenId, challenge, response);
    
    // Update last used
    if (result.success && token) {
      token.lastUsedAt = new Date();
    }
    
    // Emit event
    this.emit('token_verified', {
      tokenId,
      success: result.success,
      timestamp: new Date()
    });
    
    return result;
  }
  
  async getToken(tokenId: string): Promise<HardwareToken | null> {
    return this.registeredTokens.get(tokenId) || null;
  }
  
  async getUserTokens(userId: string): Promise<HardwareToken[]> {
    const tokenIds = this.userTokens.get(userId);
    
    if (!tokenIds) {
      return [];
    }
    
    const tokens: HardwareToken[] = [];
    
    for (const tokenId of tokenIds) {
      const token = this.registeredTokens.get(tokenId);
      if (token) {
        tokens.push(token);
      }
    }
    
    return tokens;
  }
  
  async removeToken(tokenId: string): Promise<boolean> {
    const token = this.registeredTokens.get(tokenId);
    
    if (!token) {
      return false;
    }
    
    // Remove from registrations
    this.registeredTokens.delete(tokenId);
    
    // Remove from user associations
    for (const [userId, tokenIds] of this.userTokens.entries()) {
      if (tokenIds.has(tokenId)) {
        tokenIds.delete(tokenId);
        if (tokenIds.size === 0) {
          this.userTokens.delete(userId);
        }
        break;
      }
    }
    
    // Emit event
    this.emit('token_removed', {
      tokenId,
      timestamp: new Date()
    });
    
    return true;
  }
  
  getSupportedTypes(): TokenType[] {
    return Array.from(this.providers.keys());
  }
  
  isTypeSupported(type: TokenType): boolean {
    return this.providers.has(type);
  }
  
  // For testing
  getMockProvider(): MockHardwareTokenProvider | null {
    const provider = this.providers.get('mock');
    if (provider instanceof MockHardwareTokenProvider) {
      return provider;
    }
    return null;
  }
  
  // Statistics
  getStats(): {
    totalTokens: number;
    tokensByType: Record<TokenType, number>;
    usersWithTokens: number;
  } {
    const tokensByType: Record<string, number> = {};
    
    for (const token of this.registeredTokens.values()) {
      tokensByType[token.type] = (tokensByType[token.type] || 0) + 1;
    }
    
    return {
      totalTokens: this.registeredTokens.size,
      tokensByType: tokensByType as Record<TokenType, number>,
      usersWithTokens: this.userTokens.size
    };
  }
}

// Export singleton instance
let hardwareTokenService: HardwareTokenService | null = null;

export function getHardwareTokenService(): HardwareTokenService {
  if (!hardwareTokenService) {
    hardwareTokenService = new HardwareTokenService();
  }
  return hardwareTokenService;
}