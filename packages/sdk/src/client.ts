import {
  PlintoConfig,
  AuthTokens,
  User,
  SignInCredentials,
  SignUpCredentials,
  PasswordResetRequest,
  PasswordResetConfirmation,
  ChangePasswordRequest,
  UpdateUserRequest,
  Session,
  Organization,
  OrganizationMember,
  TokenIntrospection,
  MFAEnrollment,
  MFAChallenge,
  MFAVerification,
  ErrorResponse,
  PlintoError,
  PasskeyRegistration,
  EventCallback,
  PlintoEventEmitter
} from './types';

import {
  validateEmail,
  validatePassword,
  parseJWT,
  isTokenExpired,
  generateCodeVerifier,
  generateCodeChallenge,
  buildQueryString,
  parseQueryString,
  retry,
  formatError,
  StorageManager,
  generateRandomString,
  isBrowser,
  deepClone
} from './utils';

export class PlintoClient implements PlintoEventEmitter {
  private config: PlintoConfig;
  private storage: StorageManager;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private user: User | null = null;
  private listeners: Map<string, Set<EventCallback>> = new Map();
  private refreshPromise: Promise<AuthTokens> | null = null;

  constructor(config: PlintoConfig) {
    this.validateConfig(config);
    this.config = deepClone(config);
    this.storage = new StorageManager(config.storage || 'local');
    this.loadStoredTokens();
    this.setupTokenRefresh();
  }

  private validateConfig(config: PlintoConfig): void {
    if (!config) throw new Error('Configuration is required');
    if (!config.issuer) throw new Error('Issuer is required');
    if (!config.clientId) throw new Error('Client ID is required');
    if (!config.redirectUri) throw new Error('Redirect URI is required');
    
    try {
      new URL(config.issuer);
    } catch {
      throw new Error('Invalid issuer URL');
    }
  }

  private loadStoredTokens(): void {
    this.accessToken = this.storage.getItem('plinto_access_token');
    this.refreshToken = this.storage.getItem('plinto_refresh_token');
    
    if (this.accessToken) {
      const decoded = parseJWT(this.accessToken);
      if (decoded && !isTokenExpired(decoded, 60)) {
        this.emit('tokenRestored', { access_token: this.accessToken });
      } else {
        this.clearTokens();
      }
    }
  }

  private setupTokenRefresh(): void {
    if (!isBrowser()) return;
    
    setInterval(() => {
      if (this.accessToken && this.refreshToken) {
        const decoded = parseJWT(this.accessToken);
        if (decoded && isTokenExpired(decoded, 300)) {
          this.refreshAccessToken().catch(err => {
            this.emit('tokenRefreshFailed', err);
          });
        }
      }
    }, 60000); // Check every minute
  }

  // Core getters
  get issuer(): string {
    return this.config.issuer;
  }

  get clientId(): string {
    return this.config.clientId;
  }

  // Authentication methods
  async signIn(credentials: SignInCredentials): Promise<AuthTokens> {
    if (!validateEmail(credentials.email)) {
      throw this.createError('Invalid email format');
    }
    
    if (!validatePassword(credentials.password)) {
      throw this.createError('Password must be at least 8 characters');
    }
    
    const response = await this.request('/api/v1/auth/signin', {
      method: 'POST',
      body: JSON.stringify(credentials)
    });
    
    const tokens = await response.json() as AuthTokens;
    this.handleAuthResponse(tokens);
    this.emit('signIn', { user: this.user, tokens });
    return tokens;
  }

  async signUp(credentials: SignUpCredentials): Promise<User> {
    if (!validateEmail(credentials.email)) {
      throw this.createError('Invalid email format');
    }
    
    if (!validatePassword(credentials.password)) {
      throw this.createError('Password must be at least 8 characters');
    }
    
    const response = await this.request('/api/v1/auth/signup', {
      method: 'POST',
      body: JSON.stringify(credentials)
    });
    
    const user = await response.json() as User;
    this.emit('signUp', { user });
    return user;
  }

  async signOut(): Promise<{ success: boolean }> {
    if (!this.accessToken) {
      throw this.createError('No active session');
    }
    
    try {
      const response = await this.request('/api/v1/auth/signout', {
        method: 'POST'
      });
      
      const result = await response.json();
      this.clearTokens();
      this.emit('signOut', {});
      return result;
    } catch (error) {
      this.clearTokens();
      throw error;
    }
  }

  async refreshAccessToken(): Promise<AuthTokens> {
    if (!this.refreshToken) {
      throw this.createError('No refresh token available');
    }
    
    // Prevent multiple simultaneous refresh attempts
    if (this.refreshPromise) {
      return this.refreshPromise;
    }
    
    this.refreshPromise = this.request('/api/v1/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: this.refreshToken })
    }).then(async response => {
      const tokens = await response.json() as AuthTokens;
      this.handleAuthResponse(tokens);
      this.emit('tokenRefreshed', { tokens });
      return tokens;
    }).finally(() => {
      this.refreshPromise = null;
    });
    
    return this.refreshPromise;
  }

  // User management
  async getUser(): Promise<User> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/users/me');
    const user = await response.json() as User;
    this.user = user;
    return user;
  }

  async updateUser(data: UpdateUserRequest): Promise<User> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/users/me', {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
    
    const user = await response.json() as User;
    this.user = user;
    this.emit('userUpdated', { user });
    return user;
  }

  async changePassword(data: ChangePasswordRequest): Promise<{ success: boolean }> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/users/change-password', {
      method: 'POST',
      body: JSON.stringify(data)
    });
    
    return response.json();
  }

  async deleteAccount(): Promise<{ success: boolean }> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/users/me', {
      method: 'DELETE'
    });
    
    const result = await response.json();
    this.clearTokens();
    this.emit('accountDeleted', {});
    return result;
  }

  // Email verification
  async verifyEmail(token: string): Promise<{ success: boolean; email_verified: boolean }> {
    const response = await this.request('/api/v1/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token })
    });
    
    return response.json();
  }

  async sendVerificationEmail(): Promise<{ success: boolean; message: string }> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/auth/send-verification', {
      method: 'POST'
    });
    
    return response.json();
  }

  // Password reset
  async resetPassword(email: string): Promise<{ success: boolean; message: string }> {
    if (!validateEmail(email)) {
      throw this.createError('Invalid email format');
    }
    
    const response = await this.request('/api/v1/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
    
    return response.json();
  }

  async confirmPasswordReset(data: PasswordResetConfirmation): Promise<{ success: boolean }> {
    if (!validatePassword(data.password)) {
      throw this.createError('Password must be at least 8 characters');
    }
    
    const response = await this.request('/api/v1/auth/reset-password/confirm', {
      method: 'POST',
      body: JSON.stringify(data)
    });
    
    return response.json();
  }

  // Session management
  async getSessions(): Promise<Session[]> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/sessions');
    return response.json();
  }

  async revokeSession(sessionId: string): Promise<{ success: boolean }> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request(`/api/v1/sessions/${sessionId}`, {
      method: 'DELETE'
    });
    
    return response.json();
  }

  async revokeAllOtherSessions(): Promise<{ success: boolean }> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/sessions/revoke-others', {
      method: 'POST'
    });
    
    return response.json();
  }

  // Token management
  async introspectToken(): Promise<TokenIntrospection> {
    if (!this.accessToken) {
      throw this.createError('No token to introspect');
    }
    
    const response = await this.request('/api/v1/auth/introspect', {
      method: 'POST',
      body: JSON.stringify({ token: this.accessToken })
    });
    
    return response.json();
  }

  async revokeToken(): Promise<{ success: boolean }> {
    if (!this.accessToken) {
      throw this.createError('No token to revoke');
    }
    
    const response = await this.request('/api/v1/auth/revoke', {
      method: 'POST',
      body: JSON.stringify({ token: this.accessToken })
    });
    
    const result = await response.json();
    this.clearTokens();
    return result;
  }

  // MFA methods
  async enableTOTP(): Promise<MFAEnrollment> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/mfa/totp/enable', {
      method: 'POST'
    });
    
    return response.json();
  }

  async disableMFA(data: { password: string }): Promise<{ success: boolean }> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/mfa/disable', {
      method: 'POST',
      body: JSON.stringify(data)
    });
    
    return response.json();
  }

  async completeMFA(data: MFAVerification): Promise<AuthTokens> {
    const response = await this.request('/api/v1/mfa/verify', {
      method: 'POST',
      body: JSON.stringify(data)
    });
    
    const tokens = await response.json() as AuthTokens;
    this.handleAuthResponse(tokens);
    return tokens;
  }

  // Organization methods
  async getOrganizations(): Promise<Organization[]> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/organizations');
    return response.json();
  }

  async createOrganization(data: { name: string; slug?: string }): Promise<Organization> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request('/api/v1/organizations', {
      method: 'POST',
      body: JSON.stringify(data)
    });
    
    return response.json();
  }

  async switchOrganization(organizationId: string): Promise<AuthTokens> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    const response = await this.request(`/api/v1/organizations/${organizationId}/switch`, {
      method: 'POST'
    });
    
    const tokens = await response.json() as AuthTokens;
    this.handleAuthResponse(tokens);
    return tokens;
  }

  // OAuth methods
  async getAuthorizationURL(options: {
    provider?: string;
    state?: string;
    nonce?: string;
    codeChallenge?: string;
  } = {}): Promise<string> {
    const state = options.state || generateRandomString();
    const nonce = options.nonce || generateRandomString();
    
    const params = {
      client_id: this.config.clientId,
      redirect_uri: this.config.redirectUri,
      response_type: this.config.responseType || 'code',
      scope: this.config.scope || 'openid profile email',
      state,
      nonce,
      ...(options.codeChallenge && { code_challenge: options.codeChallenge }),
      ...(options.codeChallenge && { code_challenge_method: 'S256' }),
      ...(options.provider && { connection: options.provider })
    };
    
    return `${this.config.issuer}/authorize?${buildQueryString(params)}`;
  }

  async handleRedirectCallback(url: string = window.location.href): Promise<AuthTokens> {
    const urlObj = new URL(url);
    const params = parseQueryString(urlObj.search);
    
    if (params.error) {
      throw this.createError(params.error_description || params.error);
    }
    
    if (!params.code) {
      throw this.createError('Authorization code not found');
    }
    
    const response = await this.request('/api/v1/auth/token', {
      method: 'POST',
      body: JSON.stringify({
        grant_type: 'authorization_code',
        code: params.code,
        client_id: this.config.clientId,
        redirect_uri: this.config.redirectUri
      })
    });
    
    const tokens = await response.json() as AuthTokens;
    this.handleAuthResponse(tokens);
    return tokens;
  }

  // Passkey/WebAuthn methods
  async registerPasskey(name?: string): Promise<PasskeyRegistration> {
    if (!this.accessToken) {
      throw this.createError('Authentication required');
    }
    
    // Get registration options from server
    const optionsResponse = await this.request('/api/v1/passkeys/register/begin', {
      method: 'POST',
      body: JSON.stringify({ name })
    });
    
    const options = await optionsResponse.json();
    
    // Create credential using WebAuthn API
    const credential = await navigator.credentials.create(options);
    
    if (!credential) {
      throw this.createError('Failed to create passkey');
    }
    
    // Send credential to server
    const response = await this.request('/api/v1/passkeys/register/complete', {
      method: 'POST',
      body: JSON.stringify({ credential })
    });
    
    return response.json();
  }

  async signInWithPasskey(): Promise<AuthTokens> {
    // Get assertion options from server
    const optionsResponse = await this.request('/api/v1/passkeys/authenticate/begin', {
      method: 'POST'
    });
    
    const options = await optionsResponse.json();
    
    // Get credential using WebAuthn API
    const credential = await navigator.credentials.get(options);
    
    if (!credential) {
      throw this.createError('Failed to authenticate with passkey');
    }
    
    // Send credential to server
    const response = await this.request('/api/v1/passkeys/authenticate/complete', {
      method: 'POST',
      body: JSON.stringify({ credential })
    });
    
    const tokens = await response.json() as AuthTokens;
    this.handleAuthResponse(tokens);
    return tokens;
  }

  // Helper methods
  private handleAuthResponse(tokens: AuthTokens): void {
    this.setAccessToken(tokens.access_token);
    if (tokens.refresh_token) {
      this.setRefreshToken(tokens.refresh_token);
    }
    
    const decoded = parseJWT(tokens.access_token);
    if (decoded) {
      this.user = {
        id: decoded.sub,
        email: decoded.email,
        email_verified: decoded.email_verified,
        name: decoded.name,
        created_at: new Date(decoded.iat * 1000).toISOString(),
        updated_at: new Date().toISOString()
      };
    }
  }

  async request(path: string, options: RequestInit = {}): Promise<Response> {
    const url = path.startsWith('http') ? path : `${this.config.issuer}${path}`;
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers
    };
    
    if (this.accessToken && !path.includes('/auth/')) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }
    
    const response = await fetch(url, {
      ...options,
      headers
    });
    
    if (!response.ok) {
      // Handle 401 and retry with refresh token
      if (response.status === 401 && this.refreshToken && !path.includes('/auth/refresh')) {
        try {
          await this.refreshAccessToken();
          // Retry with new token
          headers['Authorization'] = `Bearer ${this.accessToken}`;
          const retryResponse = await fetch(url, {
            ...options,
            headers
          });
          
          if (!retryResponse.ok) {
            throw await this.handleErrorResponse(retryResponse);
          }
          
          return retryResponse;
        } catch (refreshError) {
          // Refresh failed, clear tokens
          this.clearTokens();
          throw refreshError;
        }
      }
      
      throw await this.handleErrorResponse(response);
    }
    
    return response;
  }

  private async handleErrorResponse(response: Response): Promise<PlintoError> {
    let errorData: ErrorResponse;
    
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        error: response.statusText || 'Request failed',
        error_description: `HTTP ${response.status}`
      };
    }
    
    const error = this.createError(
      errorData.error_description || errorData.error || 'Request failed'
    );
    
    error.code = errorData.error;
    error.status = response.status;
    error.response = errorData;
    
    // Handle rate limiting
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After');
      if (retryAfter) {
        error.message += `. Retry after ${retryAfter} seconds`;
      }
    }
    
    return error;
  }

  private createError(message: string): PlintoError {
    const error = new Error(message) as PlintoError;
    error.name = 'PlintoError';
    return error;
  }

  // Token storage
  setAccessToken(token: string | null): void {
    this.accessToken = token;
    if (token) {
      this.storage.setItem('plinto_access_token', token);
    } else {
      this.storage.removeItem('plinto_access_token');
    }
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  setRefreshToken(token: string | null): void {
    this.refreshToken = token;
    if (token) {
      this.storage.setItem('plinto_refresh_token', token);
    } else {
      this.storage.removeItem('plinto_refresh_token');
    }
  }

  getRefreshToken(): string | null {
    return this.refreshToken;
  }

  clearTokens(): void {
    this.setAccessToken(null);
    this.setRefreshToken(null);
    this.user = null;
  }

  isAuthenticated(): boolean {
    if (!this.accessToken) return false;
    
    const decoded = parseJWT(this.accessToken);
    return decoded && !isTokenExpired(decoded, 0);
  }

  // Event emitter implementation
  on(event: string, callback: EventCallback): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback: EventCallback): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }

  once(event: string, callback: EventCallback): void {
    const onceCallback: EventCallback = (event, data) => {
      callback(event, data);
      this.off(event, onceCallback);
    };
    this.on(event, onceCallback);
  }

  emit(event: string, data?: any): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => callback(event, data));
    }
  }

  // Alias for refreshAccessToken to match test expectations
  async refreshToken(): Promise<AuthTokens> {
    return this.refreshAccessToken();
  }
}

// Export default instance factory
export function createClient(config: PlintoConfig): PlintoClient {
  return new PlintoClient(config);
}