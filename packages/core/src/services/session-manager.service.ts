import { EventEmitter } from 'events';
import crypto from 'crypto';
import { createHash, createHmac } from 'crypto';

export interface Session {
  id: string;
  user_id: string;
  tenant_id?: string;
  device_id: string;
  device_fingerprint: string;
  ip_address: string;
  user_agent: string;
  location?: {
    country?: string;
    region?: string;
    city?: string;
    latitude?: number;
    longitude?: number;
  };
  created_at: Date;
  last_activity_at: Date;
  expires_at: Date;
  refresh_token: string;
  refresh_token_family: string; // For rotation tracking
  refresh_token_expires_at: Date;
  access_token_jti?: string; // Current access token ID
  is_active: boolean;
  revoked: boolean;
  revoked_at?: Date;
  revoked_reason?: string;
  security_flags: {
    mfa_verified: boolean;
    suspicious_activity: boolean;
    high_risk: boolean;
    requires_reauthentication: boolean;
  };
  metadata?: Record<string, any>;
}

export interface RefreshTokenRotationConfig {
  enabled: boolean;
  reuse_interval: number; // Grace period in seconds
  max_reuse_attempts: number;
  automatic_reuse_detection: boolean;
  family_tracking: boolean;
}

export interface SessionSecurityConfig {
  fingerprinting: {
    enabled: boolean;
    factors: string[]; // ['user_agent', 'accept_language', 'screen_resolution', etc.]
  };
  anomaly_detection: {
    enabled: boolean;
    factors: string[]; // ['location', 'time_pattern', 'device', 'behavior']
  };
  concurrent_sessions: {
    max_per_user: number;
    max_per_device: number;
    action_on_exceed: 'deny' | 'revoke_oldest' | 'alert';
  };
  geo_restrictions?: {
    allowed_countries?: string[];
    blocked_countries?: string[];
    vpn_detection: boolean;
  };
}

export interface SessionAnomalyReport {
  session_id: string;
  anomalies: SessionAnomaly[];
  risk_score: number;
  recommended_action: 'allow' | 'challenge' | 'block' | 'revoke';
  detected_at: Date;
}

export interface SessionAnomaly {
  type: 'location' | 'device' | 'time' | 'behavior' | 'velocity';
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  confidence: number; // 0-1
  details: Record<string, any>;
}

export class SessionManager extends EventEmitter {
  private sessions: Map<string, Session> = new Map();
  private refreshTokenFamilies: Map<string, Set<string>> = new Map();
  private usedRefreshTokens: Map<string, Date> = new Map();
  private userSessions: Map<string, Set<string>> = new Map();
  private deviceSessions: Map<string, Set<string>> = new Map();
  private anomalyHistory: Map<string, SessionAnomalyReport[]> = new Map();

  constructor(
    private readonly config: {
      rotation: RefreshTokenRotationConfig;
      security: SessionSecurityConfig;
      session_ttl: number; // seconds
      refresh_token_ttl: number; // seconds
      fingerprint_secret?: string;
      anomaly_threshold?: number;
    }
  ) {
    super();
    this.startCleanupTimer();
    this.startAnomalyDetection();
  }

  /**
   * Create a new session
   */
  async createSession(params: {
    user_id: string;
    tenant_id?: string;
    device_id?: string;
    ip_address: string;
    user_agent: string;
    location?: Session['location'];
    mfa_verified?: boolean;
    metadata?: Record<string, any>;
  }): Promise<Session> {
    // Check concurrent session limits
    await this.enforceSessionLimits(params.user_id, params.device_id);

    // Generate device fingerprint
    const deviceFingerprint = this.generateDeviceFingerprint({
      user_agent: params.user_agent,
      device_id: params.device_id,
      ip_address: params.ip_address
    });

    // Generate tokens
    const sessionId = crypto.randomUUID();
    const refreshToken = this.generateSecureToken();
    const refreshTokenFamily = crypto.randomUUID();

    const session: Session = {
      id: sessionId,
      user_id: params.user_id,
      tenant_id: params.tenant_id,
      device_id: params.device_id || deviceFingerprint,
      device_fingerprint: deviceFingerprint,
      ip_address: params.ip_address,
      user_agent: params.user_agent,
      location: params.location,
      created_at: new Date(),
      last_activity_at: new Date(),
      expires_at: new Date(Date.now() + this.config.session_ttl * 1000),
      refresh_token: refreshToken,
      refresh_token_family: refreshTokenFamily,
      refresh_token_expires_at: new Date(Date.now() + this.config.refresh_token_ttl * 1000),
      is_active: true,
      revoked: false,
      security_flags: {
        mfa_verified: params.mfa_verified || false,
        suspicious_activity: false,
        high_risk: false,
        requires_reauthentication: false
      },
      metadata: params.metadata
    };

    // Store session
    this.sessions.set(sessionId, session);
    
    // Track by user
    if (!this.userSessions.has(params.user_id)) {
      this.userSessions.set(params.user_id, new Set());
    }
    this.userSessions.get(params.user_id)!.add(sessionId);

    // Track by device
    const deviceKey = session.device_id;
    if (!this.deviceSessions.has(deviceKey)) {
      this.deviceSessions.set(deviceKey, new Set());
    }
    this.deviceSessions.get(deviceKey)!.add(sessionId);

    // Track refresh token family
    this.refreshTokenFamilies.set(refreshTokenFamily, new Set([refreshToken]));

    // Check for anomalies
    await this.detectAnomalies(session);

    this.emit('session:created', session);
    return session;
  }

  /**
   * Refresh session with token rotation
   */
  async refreshSession(refreshToken: string): Promise<{
    session: Session;
    access_token: string;
    refresh_token: string;
    rotation_info: {
      family: string;
      generation: number;
      rotated: boolean;
    };
  }> {
    // Find session by refresh token
    const session = this.findSessionByRefreshToken(refreshToken);
    if (!session) {
      this.emit('security:invalid-refresh-token', { token: refreshToken });
      throw new Error('Invalid refresh token');
    }

    // Check if token has expired
    if (session.refresh_token_expires_at < new Date()) {
      this.emit('security:expired-refresh-token', { session_id: session.id });
      throw new Error('Refresh token expired');
    }

    // Check if session is active
    if (!session.is_active || session.revoked) {
      throw new Error('Session is not active');
    }

    // Implement refresh token rotation
    if (this.config.rotation.enabled) {
      return await this.rotateRefreshToken(session, refreshToken);
    } else {
      // Simple refresh without rotation
      return await this.simpleRefresh(session);
    }
  }

  /**
   * Rotate refresh token with security checks
   */
  private async rotateRefreshToken(session: Session, oldToken: string): Promise<{
    session: Session;
    access_token: string;
    refresh_token: string;
    rotation_info: {
      family: string;
      generation: number;
      rotated: boolean;
    };
  }> {
    const family = session.refresh_token_family;
    const familyTokens = this.refreshTokenFamilies.get(family) || new Set();

    // Check for token reuse attack
    if (this.usedRefreshTokens.has(oldToken)) {
      const usedAt = this.usedRefreshTokens.get(oldToken)!;
      const reuseWindow = Date.now() - usedAt.getTime();
      
      if (reuseWindow > this.config.rotation.reuse_interval * 1000) {
        // Token reuse detected outside grace period - revoke entire family
        this.emit('security:refresh-token-reuse-attack', {
          session_id: session.id,
          family,
          reused_token: oldToken
        });
        
        await this.revokeTokenFamily(family);
        throw new Error('Refresh token reuse detected - session revoked');
      }
    }

    // Mark old token as used
    this.usedRefreshTokens.set(oldToken, new Date());

    // Generate new refresh token
    const newRefreshToken = this.generateSecureToken();
    
    // Update session
    session.refresh_token = newRefreshToken;
    session.refresh_token_expires_at = new Date(Date.now() + this.config.refresh_token_ttl * 1000);
    session.last_activity_at = new Date();

    // Update token family
    familyTokens.add(newRefreshToken);
    this.refreshTokenFamilies.set(family, familyTokens);

    // Generate new access token
    const accessToken = this.generateAccessToken(session);

    // Check for anomalies during refresh
    await this.detectAnomalies(session);

    this.emit('session:refreshed', {
      session_id: session.id,
      rotated: true,
      family
    });

    return {
      session,
      access_token: accessToken,
      refresh_token: newRefreshToken,
      rotation_info: {
        family,
        generation: familyTokens.size,
        rotated: true
      }
    };
  }

  /**
   * Simple refresh without rotation
   */
  private async simpleRefresh(session: Session): Promise<{
    session: Session;
    access_token: string;
    refresh_token: string;
    rotation_info: {
      family: string;
      generation: number;
      rotated: boolean;
    };
  }> {
    session.last_activity_at = new Date();
    const accessToken = this.generateAccessToken(session);

    return {
      session,
      access_token: accessToken,
      refresh_token: session.refresh_token,
      rotation_info: {
        family: session.refresh_token_family,
        generation: 1,
        rotated: false
      }
    };
  }

  /**
   * Detect anomalies in session
   */
  private async detectAnomalies(session: Session): Promise<SessionAnomalyReport | null> {
    if (!this.config.security.anomaly_detection.enabled) {
      return null;
    }

    const anomalies: SessionAnomaly[] = [];
    
    // Get user's session history
    const userSessionIds = this.userSessions.get(session.user_id) || new Set();
    const historicalSessions = Array.from(userSessionIds)
      .map(id => this.sessions.get(id))
      .filter((s): s is Session => s !== undefined && s.id !== session.id);

    // 1. Location anomaly detection
    if (this.config.security.anomaly_detection.factors.includes('location')) {
      const locationAnomaly = this.detectLocationAnomaly(session, historicalSessions);
      if (locationAnomaly) anomalies.push(locationAnomaly);
    }

    // 2. Device anomaly detection
    if (this.config.security.anomaly_detection.factors.includes('device')) {
      const deviceAnomaly = this.detectDeviceAnomaly(session, historicalSessions);
      if (deviceAnomaly) anomalies.push(deviceAnomaly);
    }

    // 3. Time pattern anomaly
    if (this.config.security.anomaly_detection.factors.includes('time_pattern')) {
      const timeAnomaly = this.detectTimeAnomaly(session, historicalSessions);
      if (timeAnomaly) anomalies.push(timeAnomaly);
    }

    // 4. Velocity anomaly (impossible travel)
    if (this.config.security.anomaly_detection.factors.includes('location')) {
      const velocityAnomaly = this.detectVelocityAnomaly(session, historicalSessions);
      if (velocityAnomaly) anomalies.push(velocityAnomaly);
    }

    if (anomalies.length === 0) {
      return null;
    }

    // Calculate risk score
    const riskScore = this.calculateSessionRiskScore(anomalies);

    // Determine recommended action
    let recommendedAction: SessionAnomalyReport['recommended_action'] = 'allow';
    if (riskScore > 0.8) {
      recommendedAction = 'revoke';
    } else if (riskScore > 0.6) {
      recommendedAction = 'block';
    } else if (riskScore > 0.4) {
      recommendedAction = 'challenge';
    }

    const report: SessionAnomalyReport = {
      session_id: session.id,
      anomalies,
      risk_score: riskScore,
      recommended_action: recommendedAction,
      detected_at: new Date()
    };

    // Store anomaly history
    if (!this.anomalyHistory.has(session.user_id)) {
      this.anomalyHistory.set(session.user_id, []);
    }
    this.anomalyHistory.get(session.user_id)!.push(report);

    // Update session security flags
    if (riskScore > 0.4) {
      session.security_flags.suspicious_activity = true;
    }
    if (riskScore > 0.6) {
      session.security_flags.high_risk = true;
    }
    if (riskScore > 0.5) {
      session.security_flags.requires_reauthentication = true;
    }

    // Emit event for monitoring
    this.emit('security:anomaly-detected', report);

    // Take automatic action if configured
    if (recommendedAction === 'revoke' && this.config.anomaly_threshold) {
      if (riskScore > this.config.anomaly_threshold) {
        await this.revokeSession(session.id, 'High risk anomaly detected');
      }
    }

    return report;
  }

  /**
   * Detect location anomaly
   */
  private detectLocationAnomaly(session: Session, historical: Session[]): SessionAnomaly | null {
    if (!session.location || historical.length === 0) return null;

    // Check if location is significantly different from historical locations
    const historicalCountries = new Set(
      historical
        .map(s => s.location?.country)
        .filter((c): c is string => c !== undefined)
    );

    if (historicalCountries.size > 0 && !historicalCountries.has(session.location.country || '')) {
      return {
        type: 'location',
        description: `Login from new country: ${session.location.country}`,
        severity: 'medium',
        confidence: 0.8,
        details: {
          new_country: session.location.country,
          historical_countries: Array.from(historicalCountries)
        }
      };
    }

    return null;
  }

  /**
   * Detect device anomaly
   */
  private detectDeviceAnomaly(session: Session, historical: Session[]): SessionAnomaly | null {
    const knownFingerprints = new Set(historical.map(s => s.device_fingerprint));

    if (knownFingerprints.size > 0 && !knownFingerprints.has(session.device_fingerprint)) {
      return {
        type: 'device',
        description: 'Login from new device',
        severity: 'low',
        confidence: 0.7,
        details: {
          new_device: session.device_fingerprint,
          user_agent: session.user_agent
        }
      };
    }

    return null;
  }

  /**
   * Detect time pattern anomaly
   */
  private detectTimeAnomaly(session: Session, historical: Session[]): SessionAnomaly | null {
    if (historical.length < 5) return null; // Need enough history

    const currentHour = session.created_at.getHours();
    const historicalHours = historical.map(s => s.created_at.getHours());
    
    // Calculate typical login hours
    const hourCounts = new Map<number, number>();
    for (const hour of historicalHours) {
      hourCounts.set(hour, (hourCounts.get(hour) || 0) + 1);
    }

    const avgHour = historicalHours.reduce((a, b) => a + b, 0) / historicalHours.length;
    const hourDeviation = Math.abs(currentHour - avgHour);

    if (hourDeviation > 6) { // More than 6 hours difference from average
      return {
        type: 'time',
        description: 'Login at unusual time',
        severity: 'low',
        confidence: 0.6,
        details: {
          current_hour: currentHour,
          typical_hours: Array.from(hourCounts.entries()).sort((a, b) => b[1] - a[1]).slice(0, 3)
        }
      };
    }

    return null;
  }

  /**
   * Detect velocity anomaly (impossible travel)
   */
  private detectVelocityAnomaly(session: Session, historical: Session[]): SessionAnomaly | null {
    if (!session.location?.latitude || !session.location?.longitude) return null;

    // Find most recent session with location
    const recentSession = historical
      .filter(s => s.location?.latitude && s.location?.longitude)
      .sort((a, b) => b.last_activity_at.getTime() - a.last_activity_at.getTime())[0];

    if (!recentSession || !recentSession.location?.latitude) return null;

    const timeDiff = (session.created_at.getTime() - recentSession.last_activity_at.getTime()) / 1000 / 3600; // hours
    const distance = this.calculateDistance(
      session.location.latitude || 0,
      session.location.longitude || 0,
      recentSession.location.latitude || 0,
      recentSession.location.longitude || 0
    );

    const velocity = distance / timeDiff; // km/h

    if (velocity > 900) { // Faster than commercial flight
      return {
        type: 'velocity',
        description: 'Impossible travel detected',
        severity: 'critical',
        confidence: 0.95,
        details: {
          distance_km: distance,
          time_hours: timeDiff,
          velocity_kmh: velocity,
          from_location: recentSession.location,
          to_location: session.location
        }
      };
    }

    return null;
  }

  /**
   * Calculate distance between two coordinates (Haversine formula)
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
   * Calculate session risk score
   */
  private calculateSessionRiskScore(anomalies: SessionAnomaly[]): number {
    let score = 0;
    let totalWeight = 0;

    const severityWeights = {
      low: 0.2,
      medium: 0.5,
      high: 0.8,
      critical: 1.0
    };

    for (const anomaly of anomalies) {
      const weight = severityWeights[anomaly.severity] * anomaly.confidence;
      score += weight;
      totalWeight += 1;
    }

    return totalWeight > 0 ? Math.min(score / totalWeight, 1.0) : 0;
  }

  /**
   * Revoke a session
   */
  async revokeSession(sessionId: string, reason?: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (!session) return;

    session.revoked = true;
    session.revoked_at = new Date();
    session.revoked_reason = reason;
    session.is_active = false;

    this.emit('session:revoked', {
      session_id: sessionId,
      reason
    });
  }

  /**
   * Revoke entire token family (for security breach)
   */
  private async revokeTokenFamily(family: string): Promise<void> {
    const tokens = this.refreshTokenFamilies.get(family) || new Set();
    
    // Find and revoke all sessions in this family
    for (const [sessionId, session] of this.sessions) {
      if (session.refresh_token_family === family) {
        await this.revokeSession(sessionId, 'Token family compromised');
      }
    }

    // Clear family tracking
    this.refreshTokenFamilies.delete(family);
    
    this.emit('security:token-family-revoked', {
      family,
      affected_tokens: tokens.size
    });
  }

  /**
   * Enforce session limits
   */
  private async enforceSessionLimits(userId: string, deviceId?: string): Promise<void> {
    const config = this.config.security.concurrent_sessions;

    // Check per-user limit
    const userSessionIds = this.userSessions.get(userId) || new Set();
    const activeSessions = Array.from(userSessionIds)
      .map(id => this.sessions.get(id))
      .filter((s): s is Session => s !== undefined && s.is_active && !s.revoked);

    if (activeSessions.length >= config.max_per_user) {
      switch (config.action_on_exceed) {
        case 'deny':
          throw new Error('Maximum concurrent sessions exceeded');
        case 'revoke_oldest':
          const oldest = activeSessions.sort((a, b) => 
            a.created_at.getTime() - b.created_at.getTime()
          )[0];
          await this.revokeSession(oldest.id, 'Exceeded session limit');
          break;
        case 'alert':
          this.emit('security:session-limit-exceeded', {
            user_id: userId,
            current_sessions: activeSessions.length
          });
          break;
      }
    }

    // Check per-device limit
    if (deviceId) {
      const deviceSessionIds = this.deviceSessions.get(deviceId) || new Set();
      const activeDeviceSessions = Array.from(deviceSessionIds)
        .map(id => this.sessions.get(id))
        .filter((s): s is Session => s !== undefined && s.is_active && !s.revoked);

      if (activeDeviceSessions.length >= config.max_per_device) {
        throw new Error('Maximum device sessions exceeded');
      }
    }
  }

  /**
   * Generate secure token
   */
  private generateSecureToken(): string {
    return crypto.randomBytes(32).toString('base64url');
  }

  /**
   * Generate access token (simplified - in production use JWT)
   */
  private generateAccessToken(session: Session): string {
    const payload = {
      jti: crypto.randomUUID(),
      sub: session.user_id,
      sid: session.id,
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 3600 // 1 hour
    };

    // In production, sign with private key
    return Buffer.from(JSON.stringify(payload)).toString('base64url');
  }

  /**
   * Generate device fingerprint
   */
  private generateDeviceFingerprint(params: {
    user_agent: string;
    device_id?: string;
    ip_address: string;
  }): string {
    const data = `${params.device_id || ''}:${params.user_agent}:${params.ip_address}`;
    const secret = this.config.fingerprint_secret || 'default-secret';
    return createHmac('sha256', secret).update(data).digest('hex');
  }

  /**
   * Find session by refresh token
   */
  private findSessionByRefreshToken(refreshToken: string): Session | undefined {
    for (const session of this.sessions.values()) {
      if (session.refresh_token === refreshToken) {
        return session;
      }
    }
    return undefined;
  }

  /**
   * Start cleanup timer
   */
  private startCleanupTimer(): void {
    setInterval(() => {
      this.cleanup();
    }, 60000); // Every minute
  }

  /**
   * Start anomaly detection monitoring
   */
  private startAnomalyDetection(): void {
    setInterval(() => {
      this.performPeriodicAnomalyAnalysis();
    }, 300000); // Every 5 minutes
  }

  /**
   * Cleanup expired sessions and tokens
   */
  private cleanup(): void {
    const now = new Date();

    // Clean expired sessions
    for (const [id, session] of this.sessions) {
      if (session.expires_at < now || session.refresh_token_expires_at < now) {
        this.sessions.delete(id);
        
        // Clean from user sessions
        const userSessions = this.userSessions.get(session.user_id);
        if (userSessions) {
          userSessions.delete(id);
        }

        // Clean from device sessions
        const deviceSessions = this.deviceSessions.get(session.device_id);
        if (deviceSessions) {
          deviceSessions.delete(id);
        }
      }
    }

    // Clean old used refresh tokens (keep for 7 days for audit)
    const cutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    for (const [token, usedAt] of this.usedRefreshTokens) {
      if (usedAt < cutoff) {
        this.usedRefreshTokens.delete(token);
      }
    }
  }

  /**
   * Perform periodic anomaly analysis
   */
  private performPeriodicAnomalyAnalysis(): void {
    for (const [userId, reports] of this.anomalyHistory) {
      // Keep only recent reports (last 24 hours)
      const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000);
      const recentReports = reports.filter(r => r.detected_at > cutoff);
      
      if (recentReports.length !== reports.length) {
        this.anomalyHistory.set(userId, recentReports);
      }

      // Check for patterns in anomalies
      if (recentReports.length > 5) {
        this.emit('security:anomaly-pattern-detected', {
          user_id: userId,
          anomaly_count: recentReports.length,
          avg_risk_score: recentReports.reduce((sum, r) => sum + r.risk_score, 0) / recentReports.length
        });
      }
    }
  }

  /**
   * Get session statistics
   */
  getStatistics(): {
    total_sessions: number;
    active_sessions: number;
    revoked_sessions: number;
    unique_users: number;
    unique_devices: number;
    high_risk_sessions: number;
    token_families: number;
  } {
    const stats = {
      total_sessions: this.sessions.size,
      active_sessions: 0,
      revoked_sessions: 0,
      unique_users: this.userSessions.size,
      unique_devices: this.deviceSessions.size,
      high_risk_sessions: 0,
      token_families: this.refreshTokenFamilies.size
    };

    for (const session of this.sessions.values()) {
      if (session.is_active && !session.revoked) {
        stats.active_sessions++;
      }
      if (session.revoked) {
        stats.revoked_sessions++;
      }
      if (session.security_flags.high_risk) {
        stats.high_risk_sessions++;
      }
    }

    return stats;
  }
}