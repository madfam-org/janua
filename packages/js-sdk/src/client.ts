import { HttpClient } from './utils/http';
import { createStorage, StorageAdapter } from './utils/storage';
import { AuthClient } from './auth';
import { UserClient } from './users';
import { OrganizationClient } from './organizations';
import { PlintoConfig, User, Session } from './types';

export class PlintoClient {
  private config: PlintoConfig;
  private http: HttpClient;
  private storage: StorageAdapter;
  
  public auth: AuthClient;
  public users: UserClient;
  public organizations: OrganizationClient;

  constructor(config: PlintoConfig) {
    this.validateConfig(config);
    this.config = {
      apiUrl: 'https://api.plinto.dev',
      debug: false,
      ...config,
    };

    // Initialize storage
    this.storage = createStorage();

    // Initialize HTTP client
    const headers: HeadersInit = {};
    if (this.config.apiKey) {
      headers['X-API-Key'] = this.config.apiKey;
    }
    headers['X-App-Id'] = this.config.appId;

    this.http = new HttpClient(this.config.apiUrl!, headers, this.config.debug);

    // Initialize sub-clients
    this.auth = new AuthClient(this.http, this.storage);
    this.users = new UserClient(this.http);
    this.organizations = new OrganizationClient(this.http);
  }

  private validateConfig(config: PlintoConfig): void {
    if (!config.appId) {
      throw new Error('appId is required in Plinto configuration');
    }

    if (config.apiUrl) {
      try {
        new URL(config.apiUrl);
      } catch {
        throw new Error('Invalid apiUrl provided in Plinto configuration');
      }
    }
  }

  /**
   * Get the current authenticated user
   */
  getUser(): User | null {
    return this.auth.getUser();
  }

  /**
   * Get the current session
   */
  getSession(): Session | null {
    return this.auth.getSession();
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return this.auth.isAuthenticated();
  }

  /**
   * Sign out and clear session
   */
  async signOut(): Promise<void> {
    await this.auth.signOut();
  }

  /**
   * Update the current session and user data
   */
  async updateSession(): Promise<void> {
    await this.auth.updateSession();
  }

  /**
   * Set a custom API URL (useful for development)
   */
  setApiUrl(url: string): void {
    try {
      new URL(url);
      this.config.apiUrl = url;
      this.http = new HttpClient(url, this.http['headers'], this.config.debug);
      
      // Reinitialize clients with new HTTP instance
      this.auth = new AuthClient(this.http, this.storage);
      this.users = new UserClient(this.http);
      this.organizations = new OrganizationClient(this.http);
    } catch {
      throw new Error('Invalid API URL');
    }
  }

  /**
   * Enable or disable debug mode
   */
  setDebugMode(enabled: boolean): void {
    this.config.debug = enabled;
    this.http = new HttpClient(this.config.apiUrl!, this.http['headers'], enabled);
    
    // Reinitialize clients
    this.auth = new AuthClient(this.http, this.storage);
    this.users = new UserClient(this.http);
    this.organizations = new OrganizationClient(this.http);
  }

  /**
   * Clean up resources (timers, storage, etc.)
   */
  destroy(): void {
    this.auth.destroy();
    this.storage.clear();
  }

  /**
   * Helper method to handle authentication redirects
   */
  async handleRedirectCallback(): Promise<void> {
    if (typeof window === 'undefined') {
      throw new Error('handleRedirectCallback can only be used in browser environments');
    }

    const url = new URL(window.location.href);
    
    // Handle OAuth callback
    const code = url.searchParams.get('code');
    const state = url.searchParams.get('state');
    if (code && state) {
      await this.auth.handleOAuthCallback(code, state);
      // Clean up URL
      url.searchParams.delete('code');
      url.searchParams.delete('state');
      window.history.replaceState({}, '', url.toString());
      return;
    }

    // Handle magic link
    const magicToken = url.searchParams.get('magic_token');
    if (magicToken) {
      await this.auth.signInWithMagicLink(magicToken);
      // Clean up URL
      url.searchParams.delete('magic_token');
      window.history.replaceState({}, '', url.toString());
      return;
    }

    // Handle email verification
    const verifyToken = url.searchParams.get('verify_token');
    if (verifyToken) {
      await this.auth.verifyEmail({ token: verifyToken });
      // Clean up URL
      url.searchParams.delete('verify_token');
      window.history.replaceState({}, '', url.toString());
      return;
    }
  }

  /**
   * Check if the current URL contains authentication parameters
   */
  hasAuthParams(): boolean {
    if (typeof window === 'undefined') {
      return false;
    }

    const url = new URL(window.location.href);
    return !!(
      (url.searchParams.get('code') && url.searchParams.get('state')) ||
      url.searchParams.get('magic_token') ||
      url.searchParams.get('verify_token')
    );
  }

  /**
   * Get the current Plinto configuration
   */
  getConfig(): Readonly<PlintoConfig> {
    return { ...this.config };
  }

  /**
   * Create a new instance with different configuration
   */
  static create(config: PlintoConfig): PlintoClient {
    return new PlintoClient(config);
  }
}