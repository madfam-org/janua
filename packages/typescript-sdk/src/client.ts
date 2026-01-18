/**
 * Main Janua SDK client
 */

import type {
  JanuaConfig,
  SdkEventMap,
  SdkEventType,
  SdkEventHandler,
  User,
  TokenResponse,
  Environment
} from './types';
import { HttpClient, createHttpClient } from './http-client';
import { TokenManager, EnvUtils, EventEmitter, LocalTokenStorage, SessionTokenStorage, MemoryTokenStorage, type TokenStorage } from './utils';
import { logger } from './utils/logger';
import { ConfigurationError } from './errors';
import { Auth } from './auth';
import { Users } from './users';
import { Sessions } from './sessions';
import { Organizations } from './organizations';
import { Webhooks } from './webhooks';
import { Admin } from './admin';
import { SSO } from './sso';
import { Invitations } from './invitations';
import { Payments } from './payments';
import { SCIMModule } from './scim';
import { EnterpriseFeatures, FEATURES, type LicenseInfo } from './enterprise';
import { GraphQL } from './graphql';
import { WebSocket } from './websocket';

/**
 * Main Janua SDK client class
 */
export class JanuaClient extends EventEmitter<SdkEventMap> {
  private config: Required<JanuaConfig>;
  private tokenManager: TokenManager;
  private _httpClient: HttpClient;

  // Module instances
  public readonly auth: Auth;
  public readonly users: Users;
  public readonly sessions: Sessions;
  public readonly organizations: Organizations;
  public readonly webhooks: Webhooks;
  public readonly admin: Admin;
  public readonly sso: SSO;
  public readonly invitations: Invitations;
  public readonly payments: Payments;
  public readonly scim: SCIMModule;

  // Real-time features
  public readonly graphql?: GraphQL;
  public readonly ws?: WebSocket;

  // Enterprise features
  private enterprise: EnterpriseFeatures;
  private licenseInfo?: LicenseInfo;

  /**
   * Get the HTTP client for making raw API requests.
   * Used by plugins to make API calls.
   */
  get http(): HttpClient {
    return this._httpClient;
  }

  constructor(config: Partial<JanuaConfig> = {}) {
    super();

    // Validate and merge configuration
    this.config = this.validateAndMergeConfig(config);

    // Initialize token manager
    this.tokenManager = this.createTokenManager();

    // Initialize HTTP client
    this._httpClient = this.createHttpClient();

    // Initialize enterprise features
    this.enterprise = new EnterpriseFeatures({
      licenseKey: (config as any).licenseKey,
      apiUrl: this.config.baseURL
    });

    // Initialize modules
    this.auth = new Auth(
      this._httpClient,
      this.tokenManager,
      () => this.emit('auth:signedIn', { user: {} as any }),
      () => this.emit('auth:signedOut', {})
    );
    this.users = new Users(this._httpClient);
    this.sessions = new Sessions(this._httpClient);
    this.organizations = new Organizations(this._httpClient);
    this.webhooks = new Webhooks(this._httpClient);
    this.admin = new Admin(this._httpClient);
    this.sso = new SSO(this._httpClient);
    this.invitations = new Invitations(this._httpClient);
    this.payments = new Payments(this._httpClient);
    this.scim = new SCIMModule(this._httpClient);

    // Initialize GraphQL if configured
    if ((config as any).graphqlUrl) {
      this.graphql = new GraphQL({
        httpUrl: (config as any).graphqlUrl,
        wsUrl: (config as any).graphqlWsUrl,
        getAuthToken: () => this.getAccessToken(),
        debug: this.config.debug,
      });
    }

    // Initialize WebSocket if configured
    if ((config as any).wsUrl) {
      this.ws = new WebSocket({
        url: (config as any).wsUrl,
        getAuthToken: () => this.getAccessToken(),
        reconnect: (config as any).wsReconnect ?? true,
        reconnectInterval: (config as any).wsReconnectInterval || 5000,
        reconnectAttempts: (config as any).wsReconnectAttempts || 5,
        heartbeatInterval: (config as any).wsHeartbeatInterval || 30000,
        debug: this.config.debug,
      });

      // Auto-connect WebSocket
      if ((config as any).wsAutoConnect !== false) {
        this.ws.connect().catch((err) => logger.warn('WebSocket auto-connect failed:', err));
      }
    }

    // Set up event forwarding
    this.setupEventForwarding();

    // Validate license on initialization if provided
    if ((config as any).licenseKey) {
      this.validateLicense().catch((err) => logger.warn('License validation failed:', err));
    }

    // Auto-refresh tokens if enabled
    if (this.config.autoRefreshTokens) {
      this.setupAutoTokenRefresh();
    }
  }

  /**
   * Validate and merge configuration with defaults
   */
  private validateAndMergeConfig(config: Partial<JanuaConfig>): Required<JanuaConfig> {
    // Validate required configuration
    if (!config.baseURL) {
      throw new ConfigurationError('baseURL is required');
    }

    // Set defaults (exclude optional fields from Required type to avoid type conflicts)
    const defaults = {
      baseURL: '',
      apiKey: '',
      timeout: 30000,
      retryAttempts: 3,
      retryDelay: 1000,
      environment: 'development' as Environment,
      debug: false,
      autoRefreshTokens: true,
      tokenStorage: 'localStorage' as const,
      customStorage: undefined
    };

    const mergedConfig = { ...defaults, ...config } as Required<JanuaConfig>;

    // Validate baseURL format
    try {
      new URL(mergedConfig.baseURL);
    } catch {
      throw new ConfigurationError('Invalid baseURL format');
    }

    // Validate timeout
    if (mergedConfig.timeout <= 0) {
      throw new ConfigurationError('Timeout must be greater than 0');
    }

    // Validate retry attempts
    if (mergedConfig.retryAttempts < 0) {
      throw new ConfigurationError('Retry attempts must be non-negative');
    }

    // Validate retry delay
    if (mergedConfig.retryDelay <= 0) {
      throw new ConfigurationError('Retry delay must be greater than 0');
    }

    return mergedConfig;
  }

  /**
   * Create token manager instance
   */
  private createTokenManager(): TokenManager {
    let storage: TokenStorage;

    if (this.config.customStorage) {
      // Wrap custom storage to ensure it conforms to TokenStorage interface
      const custom = this.config.customStorage;
      storage = {
        async getItem(key: string): Promise<string | null> {
          const result = custom.getItem(key);
          return result instanceof Promise ? result : Promise.resolve(result);
        },
        async setItem(key: string, value: string): Promise<void> {
          const result = custom.setItem(key, value);
          return result instanceof Promise ? result : Promise.resolve(result);
        },
        async removeItem(key: string): Promise<void> {
          const result = custom.removeItem(key);
          return result instanceof Promise ? result : Promise.resolve(result);
        }
      };
    } else if (this.config.tokenStorage) {
      // Use specified storage type
      switch (this.config.tokenStorage) {
        case 'localStorage':
          storage = new LocalTokenStorage();
          break;
        case 'sessionStorage':
          storage = new SessionTokenStorage();
          break;
        case 'memory':
          storage = new MemoryTokenStorage();
          break;
        default:
          storage = EnvUtils.getDefaultStorage();
      }
    } else {
      storage = EnvUtils.getDefaultStorage();
    }

    return new TokenManager(storage);
  }

  /**
   * Create HTTP client instance
   */
  private createHttpClient(): HttpClient {
    const client = createHttpClient(this.config, this.tokenManager);
    // Ensure we return HttpClient type (both HttpClient and AxiosHttpClient are compatible)
    return client as HttpClient;
  }

  /**
   * Set up event forwarding from HTTP client
   */
  private setupEventForwarding(): void {
    this._httpClient.on('token:refreshed', (data) => {
      this.emit('token:refreshed', data);
    });

    this._httpClient.on('token:expired', (data) => {
      this.emit('token:expired', data);
    });

    this._httpClient.on('auth:signedIn', (data) => {
      this.emit('auth:signedIn', data);
    });

    this._httpClient.on('auth:signedOut', (data) => {
      this.emit('auth:signedOut', data);
    });

    this._httpClient.on('error', (data) => {
      this.emit('error', data);
    });
  }

  /**
   * Set up automatic token refresh
   */
  private setupAutoTokenRefresh(): void {
    const checkAndRefresh = async () => {
      try {
        const tokenData = await this.tokenManager.getTokenData();
        if (!tokenData) return;

        // Check if token expires within 5 minutes
        const expiresIn = tokenData.expires_at - Date.now();
        const fiveMinutes = 5 * 60 * 1000;

        if (expiresIn <= fiveMinutes && expiresIn > 0) {
          await this.auth.refreshToken({ refresh_token: tokenData.refresh_token });
        }
      } catch (error) {
        this.emit('error', { error });
      }
    };

    // Check every minute
    setInterval(checkAndRefresh, 60 * 1000);
  }

  // Authentication State Methods

  /**
   * Check if user is currently authenticated
   */
  async isAuthenticated(): Promise<boolean> {
    return await this.tokenManager.hasValidTokens();
  }

  /**
   * Check if user is authenticated (synchronous for backward compatibility)
   */
  isAuthenticatedSync(): boolean {
    const tokens = this.tokenManager.getTokensSync();
    return !!(tokens?.access_token);
  }

  /**
   * Get current access token
   */
  async getAccessToken(): Promise<string | null> {
    return await this.tokenManager.getAccessToken();
  }

  /**
   * Get current refresh token
   */
  async getRefreshToken(): Promise<string | null> {
    return await this.tokenManager.getRefreshToken();
  }

  /**
   * Set tokens (useful for SSO or external authentication)
   */
  async setTokens(tokens: TokenResponse): Promise<void> {
    const expiresAt = Date.now() + (tokens.expires_in * 1000);
    await this.tokenManager.setTokens({
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      expires_at: expiresAt
    });
  }

  /**
   * Clear all tokens and sign out
   */
  async signOut(): Promise<void> {
    try {
      // Try to sign out from server
      await this.auth.signOut();
    } catch {
      // Ignore server errors during sign out
    } finally {
      // Always clear local tokens
      await this.tokenManager.clearTokens();
      this.emit('auth:signedOut', {});
    }
  }

  /**
   * Get current user (if authenticated)
   */
  async getCurrentUser(): Promise<User | null> {
    try {
      if (await this.isAuthenticated()) {
        return await this.auth.getCurrentUser();
      }
      return null;
    } catch {
      return null;
    }
  }

  // Configuration Methods

  /**
   * Update configuration
   */
  updateConfig(updates: Partial<JanuaConfig>): void {
    this.config = this.validateAndMergeConfig({ ...this.config, ...updates });
  }

  /**
   * Get current configuration
   */
  getConfig(): Required<JanuaConfig> {
    return { ...this.config };
  }

  /**
   * Enable debug mode
   */
  enableDebug(): void {
    this.config.debug = true;
  }

  /**
   * Disable debug mode
   */
  disableDebug(): void {
    this.config.debug = false;
  }

  // Enterprise Methods

  /**
   * Set or update license key
   */
  setLicenseKey(key: string): void {
    this.enterprise.setLicenseKey(key);
    // Use null instead of undefined for exactOptionalPropertyTypes
    this.licenseInfo = null as any;
  }

  /**
   * Validate current license
   */
  async validateLicense(): Promise<LicenseInfo> {
    this.licenseInfo = await this.enterprise.validateLicense();
    return this.licenseInfo;
  }

  /**
   * Get current license info
   */
  getLicenseInfo(): LicenseInfo | undefined {
    return this.licenseInfo;
  }

  /**
   * Check if a feature is available
   */
  async hasFeature(feature: keyof typeof FEATURES | string): Promise<boolean> {
    const featureKey = typeof feature === 'string' && feature in FEATURES
      ? FEATURES[feature as keyof typeof FEATURES]
      : feature;
    return await this.enterprise.hasFeature(featureKey);
  }

  /**
   * Enable SSO (Enterprise feature)
   */
  async enableSSO(type: 'saml' | 'oidc', config: any): Promise<any> {
    const featureKey = type === 'saml' ? FEATURES.SSO_SAML : FEATURES.SSO_OIDC;
    await this.enterprise.requireEnterprise(featureKey);
    return await this._httpClient.post('/v1/enterprise/sso/configure', {
      type,
      config
    });
  }

  /**
   * Get audit logs (Enterprise feature)
   */
  async getAuditLogs(params?: any): Promise<any> {
    await this.enterprise.requireEnterprise(FEATURES.AUDIT_LOGS);
    return await this._httpClient.get('/v1/enterprise/audit-logs', { params });
  }

  /**
   * Create custom role (Enterprise feature)
   */
  async createCustomRole(role: any): Promise<any> {
    await this.enterprise.requireEnterprise(FEATURES.CUSTOM_ROLES);
    return await this._httpClient.post('/v1/enterprise/roles', role);
  }

  /**
   * Enable white labeling (Enterprise feature)
   */
  async configureWhiteLabeling(config: any): Promise<any> {
    await this.enterprise.requireEnterprise(FEATURES.WHITE_LABELING);
    return await this._httpClient.post('/v1/enterprise/white-label', config);
  }

  /**
   * Get compliance reports (Enterprise feature)
   */
  async getComplianceReport(type: string): Promise<any> {
    await this.enterprise.requireEnterprise(FEATURES.COMPLIANCE_REPORTS);
    return await this._httpClient.get(`/v1/enterprise/compliance/${type}`);
  }

  /**
   * Check rate limits for current operation
   */
  async checkRateLimit(operation: string): Promise<any> {
    return await this.enterprise.checkRateLimit(operation);
  }

  // Event Methods (inherited from EventEmitter but with typed interface)

  /**
   * Add event listener
   */
  override on<T extends SdkEventType>(event: T, handler: SdkEventHandler<T>): () => void {
    return super.on(event, handler);
  }

  /**
   * Add one-time event listener
   */
  override once<T extends SdkEventType>(event: T, handler: SdkEventHandler<T>): () => void {
    return super.once(event, handler);
  }

  /**
   * Remove event listener
   */
  override off<T extends SdkEventType>(event: T, handler: Function): void {
    super.off(event, handler);
  }

  /**
   * Remove all listeners for an event
   */
  override removeAllListeners(event?: SdkEventType): void {
    super.removeAllListeners(event);
  }

  // Utility Methods

  /**
   * Test API connectivity
   */
  async testConnection(): Promise<{
    success: boolean;
    latency: number;
    error?: string;
  }> {
    const startTime = Date.now();

    try {
      await this._httpClient.get('/api/v1/auth/oauth/providers', { skipAuth: true });
      const latency = Math.max(1, Date.now() - startTime);

      return {
        success: true,
        latency
      };
    } catch (error: any) {
      const latency = Math.max(1, Date.now() - startTime);

      return {
        success: false,
        latency,
        error: error.message || 'Connection failed'
      };
    }
  }

  /**
   * Get SDK version
   */
  getVersion(): string {
    return '1.0.0'; // This should be dynamically set during build
  }

  /**
   * Get SDK environment info
   */
  getEnvironmentInfo(): {
    sdk_version: string;
    environment: string;
    user_agent: string;
    base_url: string;
  } {
    return {
      sdk_version: this.getVersion(),
      environment: this.config.environment,
      user_agent: this.getUserAgent(),
      base_url: this.config.baseURL
    };
  }

  /**
   * Get user agent string
   */
  private getUserAgent(): string {
    const version = this.getVersion();

    if (EnvUtils.isBrowser()) {
      return `janua-typescript-sdk/${version} (Browser)`;
    } else if (EnvUtils.isNode()) {
      const nodeVersion = typeof process !== 'undefined' ? process.version : 'unknown';
      return `janua-typescript-sdk/${version} (Node.js ${nodeVersion})`;
    } else {
      return `janua-typescript-sdk/${version}`;
    }
  }

  // ===================================
  // Convenience methods for common operations
  // ===================================

  /**
   * Sign in a user (convenience method)
   */
  async signIn(request: import('./types').SignInRequest): Promise<import('./types').AuthResponse> {
    return this.auth.signIn(request);
  }

  /**
   * Sign up a new user (convenience method)
   */
  async signUp(request: import('./types').SignUpRequest): Promise<import('./types').AuthResponse> {
    return this.auth.signUp(request);
  }

  /**
   * Sign in with passkey (convenience method)
   */
  async signInWithPasskey(email?: string): Promise<import('./types').AuthResponse> {
    // Dynamically import WebAuthn helper for browser environments
    if (typeof window === 'undefined' || !window.PublicKeyCredential) {
      throw new ConfigurationError('Passkey authentication is only available in browser environments with WebAuthn support');
    }

    const { WebAuthnHelper } = await import('./webauthn-helper');
    const webauthnHelper = new WebAuthnHelper(this.auth);

    return await webauthnHelper.authenticateWithPasskey(email);
  }

  /**
   * Register a new passkey for the current user
   */
  async registerPasskey(name?: string): Promise<void> {
    // Dynamically import WebAuthn helper for browser environments
    if (typeof window === 'undefined' || !window.PublicKeyCredential) {
      throw new ConfigurationError('Passkey registration is only available in browser environments with WebAuthn support');
    }

    const { WebAuthnHelper } = await import('./webauthn-helper');
    const webauthnHelper = new WebAuthnHelper(this.auth);

    return await webauthnHelper.registerPasskey(name);
  }

  /**
   * Update current user (convenience method)
   */
  async updateUser(request: import('./types').UserUpdateRequest): Promise<User> {
    return this.users.updateCurrentUser(request);
  }

  /**
   * Destroy the client and cleanup resources
   */
  destroy(): void {
    this.removeAllListeners();

    // Note: We don't clear tokens here as that would sign out the user
    // Use signOut() if you want to clear tokens
  }
}

/**
 * Create a new Janua client instance
 */
export function createClient(config: Partial<JanuaConfig> = {}): JanuaClient {
  return new JanuaClient(config);
}

/**
 * Default export
 */
export default JanuaClient;
