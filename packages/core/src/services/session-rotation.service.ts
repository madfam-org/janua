/**
 * Session Refresh Token Rotation Service
 * Implements secure token rotation for enhanced security
 */

import { EventEmitter } from 'events';
import { randomBytes } from 'crypto';
import jwt from 'jsonwebtoken';

export interface SessionToken {
  accessToken: string;
  refreshToken: string;
  accessTokenExpiry: Date;
  refreshTokenExpiry: Date;
}

export interface RefreshTokenPayload {
  userId: string;
  sessionId: string;
  tokenFamily: string;
  version: number;
  issuedAt: number;
  expiresAt: number;
}

export interface SessionRotationConfig {
  accessTokenTTL?: number; // in seconds, default 15 minutes
  refreshTokenTTL?: number; // in seconds, default 7 days
  rotateRefreshToken?: boolean; // default true
  reuseWindow?: number; // in seconds, default 10 seconds
  maxTokenFamilySize?: number; // default 5
  jwtSecret: string;
  issuer?: string;
}

export class SessionRotationService extends EventEmitter {
  private config: Required<SessionRotationConfig>;
  private tokenFamilies: Map<string, Set<string>> = new Map();
  private usedTokens: Map<string, number> = new Map();
  private redisService: any;

  constructor(config: SessionRotationConfig, redisService?: any) {
    super();
    this.config = {
      accessTokenTTL: config.accessTokenTTL || 900, // 15 minutes
      refreshTokenTTL: config.refreshTokenTTL || 604800, // 7 days
      rotateRefreshToken: config.rotateRefreshToken !== false,
      reuseWindow: config.reuseWindow || 10, // 10 seconds
      maxTokenFamilySize: config.maxTokenFamilySize || 5,
      jwtSecret: config.jwtSecret,
      issuer: config.issuer || 'janua',
    };
    this.redisService = redisService;
  }

  /**
   * Create initial session with tokens
   */
  async createSession(userId: string, metadata?: Record<string, any>): Promise<SessionToken> {
    const sessionId = this.generateSessionId();
    const tokenFamily = this.generateTokenFamily();

    // Create access token
    const accessToken = this.generateAccessToken(userId, sessionId, metadata);
    const accessTokenExpiry = new Date(Date.now() + this.config.accessTokenTTL * 1000);

    // Create refresh token
    const refreshTokenPayload: RefreshTokenPayload = {
      userId,
      sessionId,
      tokenFamily,
      version: 1,
      issuedAt: Math.floor(Date.now() / 1000),
      expiresAt: Math.floor(Date.now() / 1000) + this.config.refreshTokenTTL,
    };

    const refreshToken = jwt.sign(refreshTokenPayload, this.config.jwtSecret, {
      issuer: this.config.issuer,
      expiresIn: this.config.refreshTokenTTL,
    });

    const refreshTokenExpiry = new Date(Date.now() + this.config.refreshTokenTTL * 1000);

    // Store token family
    if (!this.tokenFamilies.has(tokenFamily)) {
      this.tokenFamilies.set(tokenFamily, new Set());
    }
    this.tokenFamilies.get(tokenFamily)!.add(refreshToken);

    // Store in Redis if available
    if (this.redisService) {
      await this.storeSessionInRedis(sessionId, {
        userId,
        tokenFamily,
        version: 1,
        metadata,
        createdAt: new Date().toISOString(),
      });
    }

    this.emit('session:created', { userId, sessionId, tokenFamily });

    return {
      accessToken,
      refreshToken,
      accessTokenExpiry,
      refreshTokenExpiry,
    };
  }

  /**
   * Refresh tokens with rotation
   */
  async refreshTokens(refreshToken: string): Promise<SessionToken> {
    try {
      // Verify refresh token
      const payload = jwt.verify(refreshToken, this.config.jwtSecret, {
        issuer: this.config.issuer,
      }) as RefreshTokenPayload;

      // Check if token has been used recently (reuse detection)
      const lastUsed = this.usedTokens.get(refreshToken);
      if (lastUsed) {
        const timeSinceLastUse = (Date.now() - lastUsed) / 1000;
        
        if (timeSinceLastUse < this.config.reuseWindow) {
          // Token reuse detected within window - possible attack
          await this.revokeTokenFamily(payload.tokenFamily);
          throw new Error('Token reuse detected - session revoked for security');
        }
      }

      // Check token family validity
      const family = this.tokenFamilies.get(payload.tokenFamily);
      if (!family || !family.has(refreshToken)) {
        throw new Error('Invalid token family or token not found');
      }

      // Mark token as used
      this.usedTokens.set(refreshToken, Date.now());

      // Generate new tokens
      const newAccessToken = this.generateAccessToken(
        payload.userId,
        payload.sessionId
      );
      const accessTokenExpiry = new Date(Date.now() + this.config.accessTokenTTL * 1000);

      let newRefreshToken = refreshToken;
      let refreshTokenExpiry = new Date(payload.expiresAt * 1000);

      // Rotate refresh token if enabled
      if (this.config.rotateRefreshToken) {
        const newPayload: RefreshTokenPayload = {
          ...payload,
          version: payload.version + 1,
          issuedAt: Math.floor(Date.now() / 1000),
          expiresAt: Math.floor(Date.now() / 1000) + this.config.refreshTokenTTL,
        };

        newRefreshToken = jwt.sign(newPayload, this.config.jwtSecret, {
          issuer: this.config.issuer,
          expiresIn: this.config.refreshTokenTTL,
        });

        refreshTokenExpiry = new Date(Date.now() + this.config.refreshTokenTTL * 1000);

        // Update token family
        family.delete(refreshToken);
        family.add(newRefreshToken);

        // Limit token family size
        if (family.size > this.config.maxTokenFamilySize) {
          const tokensArray = Array.from(family);
          const tokensToRemove = tokensArray.slice(0, family.size - this.config.maxTokenFamilySize);
          tokensToRemove.forEach(token => {
            family.delete(token);
            this.usedTokens.delete(token);
          });
        }

        // Update session in Redis
        if (this.redisService) {
          await this.updateSessionInRedis(payload.sessionId, {
            version: newPayload.version,
            lastRefreshed: new Date().toISOString(),
          });
        }
      }

      // Clean up old used tokens
      this.cleanupUsedTokens();

      this.emit('session:refreshed', {
        userId: payload.userId,
        sessionId: payload.sessionId,
        tokenFamily: payload.tokenFamily,
        version: payload.version + 1,
      });

      return {
        accessToken: newAccessToken,
        refreshToken: newRefreshToken,
        accessTokenExpiry,
        refreshTokenExpiry,
      };
    } catch (error: any) {
      this.emit('session:refresh-failed', { error: error.message });
      throw error;
    }
  }

  /**
   * Revoke a specific session
   */
  async revokeSession(sessionId: string): Promise<void> {
    // Find and revoke all tokens for this session
    if (this.redisService) {
      const session = await this.getSessionFromRedis(sessionId);
      if (session && session.tokenFamily) {
        await this.revokeTokenFamily(session.tokenFamily);
      }
      await this.deleteSessionFromRedis(sessionId);
    }

    this.emit('session:revoked', { sessionId });
  }

  /**
   * Revoke entire token family (security measure)
   */
  async revokeTokenFamily(tokenFamily: string): Promise<void> {
    const family = this.tokenFamilies.get(tokenFamily);
    if (family) {
      // Remove all tokens in family from used tokens
      family.forEach(token => {
        this.usedTokens.delete(token);
      });
      
      // Delete the entire family
      this.tokenFamilies.delete(tokenFamily);
    }

    // Store revoked family in Redis for distributed systems
    if (this.redisService) {
      await this.redisService.set(
        `revoked_family:${tokenFamily}`,
        '1',
        this.config.refreshTokenTTL
      );
    }

    this.emit('token-family:revoked', { tokenFamily });
  }

  /**
   * Validate access token
   */
  validateAccessToken(accessToken: string): any {
    try {
      return jwt.verify(accessToken, this.config.jwtSecret, {
        issuer: this.config.issuer,
      });
    } catch (error) {
      return null;
    }
  }

  /**
   * Generate access token
   */
  private generateAccessToken(
    userId: string,
    sessionId: string,
    metadata?: Record<string, any>
  ): string {
    const payload = {
      userId,
      sessionId,
      type: 'access',
      ...metadata,
    };

    return jwt.sign(payload, this.config.jwtSecret, {
      issuer: this.config.issuer,
      expiresIn: this.config.accessTokenTTL,
    });
  }

  /**
   * Generate unique session ID
   */
  private generateSessionId(): string {
    return `sess_${randomBytes(16).toString('hex')}`;
  }

  /**
   * Generate token family ID
   */
  private generateTokenFamily(): string {
    return `fam_${randomBytes(16).toString('hex')}`;
  }

  /**
   * Clean up old used tokens
   */
  private cleanupUsedTokens(): void {
    const now = Date.now();
    const maxAge = this.config.refreshTokenTTL * 1000;

    for (const [token, timestamp] of this.usedTokens.entries()) {
      if (now - timestamp > maxAge) {
        this.usedTokens.delete(token);
      }
    }
  }

  /**
   * Redis storage helpers
   */
  private async storeSessionInRedis(sessionId: string, data: any): Promise<void> {
    if (!this.redisService) return;
    
    await this.redisService.set(
      `session:${sessionId}`,
      JSON.stringify(data),
      this.config.refreshTokenTTL
    );
  }

  private async getSessionFromRedis(sessionId: string): Promise<any> {
    if (!this.redisService) return null;
    
    const data = await this.redisService.get(`session:${sessionId}`);
    return data ? JSON.parse(data) : null;
  }

  private async updateSessionInRedis(sessionId: string, updates: any): Promise<void> {
    if (!this.redisService) return;
    
    const existing = await this.getSessionFromRedis(sessionId);
    if (existing) {
      await this.storeSessionInRedis(sessionId, { ...existing, ...updates });
    }
  }

  private async deleteSessionFromRedis(sessionId: string): Promise<void> {
    if (!this.redisService) return;
    
    await this.redisService.del(`session:${sessionId}`);
  }

  /**
   * Get session info
   */
  async getSessionInfo(sessionId: string): Promise<any> {
    return this.getSessionFromRedis(sessionId);
  }

  /**
   * List all active sessions for a user
   */
  async getUserSessions(userId: string): Promise<any[]> {
    if (!this.redisService) return [];
    
    // This would need a more sophisticated Redis implementation
    // with secondary indexes or scanning
    return [];
  }
}