/**
 * Main Plinto SDK client
 */

import type {
  PlintoConfig,
  SdkEventMap,
  SdkEventType,
  SdkEventHandler,
  User,
  TokenResponse
} from './types';
import { HttpClient, AxiosHttpClient, createHttpClient } from './http-client';
import { TokenManager, EnvUtils, EventEmitter } from './utils';
import { ConfigurationError } from './errors';
import { Auth } from './auth';
import { Users } from './users';
import { Organizations } from './organizations';
import { Webhooks } from './webhooks';
import { Admin } from './admin';

/**
 * Main Plinto SDK client class
 */
export class PlintoClient extends EventEmitter<SdkEventMap> {
  private config: Required<PlintoConfig>;
  private tokenManager: TokenManager;
  private httpClient: HttpClient | AxiosHttpClient;

  // Module instances
  public readonly auth: Auth;
  public readonly users: Users;
  public readonly organizations: Organizations;
  public readonly webhooks: Webhooks;
  public readonly admin: Admin;

  constructor(config: Partial<PlintoConfig> = {}) {
    super();
    
    // Validate and merge configuration
    this.config = this.validateAndMergeConfig(config);
    
    // Initialize token manager
    this.tokenManager = this.createTokenManager();
    
    // Initialize HTTP client
    this.httpClient = this.createHttpClient();
    
    // Initialize modules
    this.auth = new Auth(this.httpClient);
    this.users = new Users(this.httpClient);
    this.organizations = new Organizations(this.httpClient);
    this.webhooks = new Webhooks(this.httpClient);
    this.admin = new Admin(this.httpClient);
    
    // Set up event forwarding
    this.setupEventForwarding();
    
    // Auto-refresh tokens if enabled
    if (this.config.autoRefreshTokens) {
      this.setupAutoTokenRefresh();
    }
  }

  /**
   * Validate and merge configuration with defaults
   */
  private validateAndMergeConfig(config: Partial<PlintoConfig>): Required<PlintoConfig> {
    // Validate required configuration
    if (!config.baseURL) {
      throw new ConfigurationError('baseURL is required');
    }

    // Set defaults
    const defaults: Required<PlintoConfig> = {
      baseURL: '',
      apiKey: undefined,
      timeout: 30000,
      retryAttempts: 3,
      retryDelay: 1000,
      environment: EnvUtils.isBrowser() ? 'browser' : 'node',
      debug: false,
      autoRefreshTokens: true,
      tokenStorage: 'localStorage',
      customStorage: undefined
    };

    const mergedConfig = { ...defaults, ...config } as Required<PlintoConfig>;

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
    let storage;

    if (this.config.customStorage) {
      storage = this.config.customStorage;
    } else {
      storage = EnvUtils.getDefaultStorage();
    }

    return new TokenManager(storage);
  }

  /**
   * Create HTTP client instance
   */
  private createHttpClient(): HttpClient | AxiosHttpClient {
    return createHttpClient(this.config, this.tokenManager);
  }

  /**
   * Set up event forwarding from HTTP client
   */
  private setupEventForwarding(): void {
    this.httpClient.on('token:refreshed', (data) => {
      this.emit('token:refreshed', data);
    });

    this.httpClient.on('token:expired', (data) => {
      this.emit('token:expired', data);
    });

    this.httpClient.on('auth:signedIn', (data) => {
      this.emit('auth:signedIn', data);
    });

    this.httpClient.on('auth:signedOut', (data) => {
      this.emit('auth:signedOut', data);
    });

    this.httpClient.on('error', (data) => {
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
  updateConfig(updates: Partial<PlintoConfig>): void {
    this.config = this.validateAndMergeConfig({ ...this.config, ...updates });
  }

  /**
   * Get current configuration
   */
  getConfig(): Required<PlintoConfig> {
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

  // Event Methods (inherited from EventEmitter but with typed interface)

  /**
   * Add event listener
   */
  on<T extends SdkEventType>(event: T, handler: SdkEventHandler<T>): () => void {
    return super.on(event, handler);
  }

  /**
   * Add one-time event listener
   */
  once<T extends SdkEventType>(event: T, handler: SdkEventHandler<T>): () => void {
    return super.once(event, handler);
  }

  /**
   * Remove all listeners for an event
   */
  off<T extends SdkEventType>(event?: T): void {
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
      await this.httpClient.get('/api/v1/auth/oauth/providers', { skipAuth: true });
      const latency = Date.now() - startTime;
      
      return {
        success: true,
        latency
      };
    } catch (error: any) {
      const latency = Date.now() - startTime;
      
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
      return `plinto-typescript-sdk/${version} (Browser)`;
    } else if (EnvUtils.isNode()) {
      const nodeVersion = typeof process !== 'undefined' ? process.version : 'unknown';
      return `plinto-typescript-sdk/${version} (Node.js ${nodeVersion})`;
    } else {
      return `plinto-typescript-sdk/${version}`;
    }
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
 * Create a new Plinto client instance
 */
export function createClient(config: Partial<PlintoConfig> = {}): PlintoClient {
  return new PlintoClient(config);
}

/**
 * Default export
 */
export default PlintoClient;