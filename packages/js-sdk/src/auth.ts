import { HttpClient } from './utils/http';
import { StorageAdapter } from './utils/storage';
import {
  User,
  Session,
  AuthTokens,
  SignUpRequest,
  SignInRequest,
  SignInResponse,
  SignUpResponse,
  PasswordResetRequest,
  PasswordResetConfirm,
  VerifyEmailRequest,
  MagicLinkRequest,
  OAuthProvider,
  PasskeyRegistrationOptions,
  PlintoError,
} from './types';

export class AuthClient {
  private http: HttpClient;
  private storage: StorageAdapter;
  private currentUser: User | null = null;
  private currentSession: Session | null = null;
  private refreshTimer?: NodeJS.Timeout;

  constructor(http: HttpClient, storage: StorageAdapter) {
    this.http = http;
    this.storage = storage;
    this.loadStoredSession();
  }

  private loadStoredSession(): void {
    const storedUser = this.storage.get('user');
    const storedSession = this.storage.get('session');
    const storedTokens = this.storage.get('tokens');

    if (storedUser && storedSession && storedTokens) {
      try {
        this.currentUser = JSON.parse(storedUser);
        this.currentSession = JSON.parse(storedSession);
        const tokens = JSON.parse(storedTokens);
        this.setAuthHeader(tokens.accessToken);
        this.scheduleTokenRefresh(tokens);
      } catch (error) {
        this.clearSession();
      }
    }
  }

  private setAuthHeader(token: string): void {
    this.http.setHeader('Authorization', `Bearer ${token}`);
  }

  private clearAuthHeader(): void {
    this.http.removeHeader('Authorization');
  }

  private storeSession(user: User, session: Session, tokens: AuthTokens): void {
    this.currentUser = user;
    this.currentSession = session;
    
    this.storage.set('user', JSON.stringify(user));
    this.storage.set('session', JSON.stringify(session));
    this.storage.set('tokens', JSON.stringify(tokens));
    
    this.setAuthHeader(tokens.accessToken);
    this.scheduleTokenRefresh(tokens);
  }

  private clearSession(): void {
    this.currentUser = null;
    this.currentSession = null;
    
    this.storage.remove('user');
    this.storage.remove('session');
    this.storage.remove('tokens');
    
    this.clearAuthHeader();
    this.cancelTokenRefresh();
  }

  private scheduleTokenRefresh(tokens: AuthTokens): void {
    this.cancelTokenRefresh();
    
    // Refresh 1 minute before expiry
    const refreshIn = Math.max((tokens.expiresIn - 60) * 1000, 0);
    
    if (refreshIn > 0) {
      this.refreshTimer = setTimeout(() => {
        this.refreshToken().catch(error => {
          console.error('Token refresh failed:', error);
          this.clearSession();
        });
      }, refreshIn);
    }
  }

  private cancelTokenRefresh(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = undefined;
    }
  }

  async signUp(request: SignUpRequest): Promise<SignUpResponse> {
    const response = await this.http.post<SignUpResponse>('/api/v1/auth/signup', request);
    this.storeSession(response.user, response.session, response.tokens);
    return response;
  }

  async signIn(request: SignInRequest): Promise<SignInResponse> {
    const response = await this.http.post<SignInResponse>('/api/v1/auth/signin', request);
    this.storeSession(response.user, response.session, response.tokens);
    return response;
  }

  async signOut(): Promise<void> {
    try {
      await this.http.post('/api/v1/auth/signout');
    } finally {
      this.clearSession();
    }
  }

  async refreshToken(): Promise<AuthTokens> {
    const storedTokens = this.storage.get('tokens');
    if (!storedTokens) {
      throw new Error('No refresh token available') as PlintoError;
    }

    const { refreshToken } = JSON.parse(storedTokens);
    const tokens = await this.http.post<AuthTokens>('/api/v1/auth/refresh', {
      refreshToken,
    });

    this.storage.set('tokens', JSON.stringify(tokens));
    this.setAuthHeader(tokens.accessToken);
    this.scheduleTokenRefresh(tokens);

    return tokens;
  }

  async requestPasswordReset(request: PasswordResetRequest): Promise<void> {
    await this.http.post('/api/v1/auth/password/reset', request);
  }

  async confirmPasswordReset(request: PasswordResetConfirm): Promise<void> {
    await this.http.post('/api/v1/auth/password/confirm', request);
  }

  async verifyEmail(request: VerifyEmailRequest): Promise<void> {
    await this.http.post('/api/v1/auth/email/verify', request);
    
    // Update current user if logged in
    if (this.currentUser) {
      this.currentUser.emailVerified = true;
      this.storage.set('user', JSON.stringify(this.currentUser));
    }
  }

  async sendMagicLink(request: MagicLinkRequest): Promise<void> {
    await this.http.post('/api/v1/auth/magic-link', request);
  }

  async signInWithMagicLink(token: string): Promise<SignInResponse> {
    const response = await this.http.post<SignInResponse>('/api/v1/auth/magic-link/verify', {
      token,
    });
    this.storeSession(response.user, response.session, response.tokens);
    return response;
  }

  async getOAuthUrl(provider: OAuthProvider): Promise<{ url: string }> {
    const params = new URLSearchParams({
      provider: provider.provider,
      ...(provider.redirectUrl && { redirect_url: provider.redirectUrl }),
      ...(provider.scopes && { scopes: provider.scopes.join(',') }),
    });

    return this.http.get(`/api/v1/auth/oauth/url?${params}`);
  }

  async handleOAuthCallback(code: string, state: string): Promise<SignInResponse> {
    const response = await this.http.post<SignInResponse>('/api/v1/auth/oauth/callback', {
      code,
      state,
    });
    this.storeSession(response.user, response.session, response.tokens);
    return response;
  }

  async beginPasskeyRegistration(options?: PasskeyRegistrationOptions): Promise<any> {
    return this.http.post('/api/v1/auth/passkeys/register/begin', options);
  }

  async completePasskeyRegistration(credential: any): Promise<void> {
    await this.http.post('/api/v1/auth/passkeys/register/complete', credential);
  }

  async beginPasskeyAuthentication(): Promise<any> {
    return this.http.post('/api/v1/auth/passkeys/authenticate/begin');
  }

  async completePasskeyAuthentication(credential: any): Promise<SignInResponse> {
    const response = await this.http.post<SignInResponse>(
      '/api/v1/auth/passkeys/authenticate/complete',
      credential
    );
    this.storeSession(response.user, response.session, response.tokens);
    return response;
  }

  async enableMFA(type: 'totp' | 'sms'): Promise<{ secret?: string; qrCode?: string }> {
    return this.http.post('/api/v1/auth/mfa/enable', { type });
  }

  async confirmMFA(code: string): Promise<void> {
    await this.http.post('/api/v1/auth/mfa/confirm', { code });
  }

  async disableMFA(code: string): Promise<void> {
    await this.http.post('/api/v1/auth/mfa/disable', { code });
  }

  async verifyMFA(code: string): Promise<AuthTokens> {
    const tokens = await this.http.post<AuthTokens>('/api/v1/auth/mfa/verify', { code });
    
    const storedTokens = this.storage.get('tokens');
    if (storedTokens) {
      const existingTokens = JSON.parse(storedTokens);
      const updatedTokens = { ...existingTokens, ...tokens };
      this.storage.set('tokens', JSON.stringify(updatedTokens));
      this.setAuthHeader(updatedTokens.accessToken);
      this.scheduleTokenRefresh(updatedTokens);
    }

    return tokens;
  }

  getUser(): User | null {
    return this.currentUser;
  }

  getSession(): Session | null {
    return this.currentSession;
  }

  isAuthenticated(): boolean {
    return this.currentUser !== null && this.currentSession !== null;
  }

  async updateSession(): Promise<void> {
    if (!this.isAuthenticated()) {
      throw new Error('Not authenticated') as PlintoError;
    }

    const [user, session] = await Promise.all([
      this.http.get<User>('/api/v1/auth/me'),
      this.http.get<Session>('/api/v1/auth/session'),
    ]);

    this.currentUser = user;
    this.currentSession = session;
    
    this.storage.set('user', JSON.stringify(user));
    this.storage.set('session', JSON.stringify(session));
  }

  destroy(): void {
    this.clearSession();
  }
}