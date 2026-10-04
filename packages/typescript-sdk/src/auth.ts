/**
 * Authentication module for the Janua TypeScript SDK
 */

import type { HttpClient } from './http-client';
import type {
  SignUpRequest,
  SignInRequest,
  RefreshTokenRequest,
  ForgotPasswordRequest,
  MagicLinkRequest,
  AuthResponse,
  AuthApiResponse,
  TokenResponse,
  User,
  UserUpdateRequest,
  MFAEnableResponse,
  MFAVerifyRequest,
  MFAStatusResponse,
  MFABackupCodesResponse,
  OAuthProvider,
  OAuthProvidersResponse,
  LinkedAccountsResponse,
  Passkey,
  PublicKeyCredentialJSON
} from './types';
import { AuthenticationError, ValidationError } from './errors';
import {
  ValidationUtils,
  TokenManager,
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  storePKCEParams,
  retrievePKCEParams,
  clearPKCEParams,
  validateState,
  buildJanuaAuthorizeUrl,
  stripTrailingSlashes,
} from './utils';

/**
 * Options for initiating the "Sign in with Janua" OIDC flow.
 */
export interface JanuaSSOOptions {
  /** Registered OAuth `client_id` for this consuming app (required). */
  clientId: string;
  /** Redirect URI registered for `clientId`; where Janua returns `code`+`state`. */
  redirectUri: string;
  /** OIDC scopes. Defaults to `['openid', 'profile', 'email']`. */
  scopes?: string[];
  /** CSRF state. Auto-generated (and persisted) when omitted. */
  state?: string;
  /** OIDC nonce for replay protection of the id_token. */
  nonce?: string;
  /** OIDC `prompt` (e.g. `'none'` for silent auth on first-party clients). */
  prompt?: string;
  /**
   * Override the Janua issuer base URL. Defaults to the client's configured
   * `baseURL`. Only needed when the SDK client points somewhere else.
   */
  baseUrl?: string;
}

/**
 * Result of building the Janua OIDC authorize URL.
 */
export interface JanuaAuthorizeUrlResult {
  /** Fully-built `GET /api/v1/oauth/authorize` URL to redirect the browser to. */
  url: string;
  /** The `state` value persisted for callback validation. */
  state: string;
  /** The PKCE `code_verifier` persisted for the token exchange. */
  codeVerifier: string;
}

/**
 * Token response from the Janua OIDC token endpoint.
 */
export interface JanuaSSOTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string;
  id_token?: string;
  scope?: string;
}

/**
 * Authentication operations
 */
export class Auth {
  constructor(
    private http: HttpClient,
    private tokenManager: TokenManager,
    private onSignIn?: (data?: { user: User }) => void,
    private onSignOut?: () => void,
    /**
     * Janua issuer base URL. Required for the OIDC "Sign in with Janua" flow
     * ({@link initiateJanuaSSO}), which builds absolute redirect/token URLs.
     */
    private baseUrl: string = ''
  ) {}

  /**
   * Sign up a new user
   */
  async signUp(request: SignUpRequest): Promise<AuthResponse> {
    // Validate input
    if (!ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    const passwordValidation = ValidationUtils.validatePassword(request.password);
    if (!passwordValidation.isValid) {
      throw new ValidationError('Password validation failed',
        passwordValidation.errors.map(err => ({ field: 'password', message: err }))
      );
    }

    if (request.username && !ValidationUtils.isValidUsername(request.username)) {
      throw new ValidationError('Invalid username format');
    }

    const response = await this.http.post<AuthApiResponse>('/api/v1/auth/register', request);

    // Extract tokens - support both nested (API actual) and flat (legacy) structures
    const tokens = response.data.tokens || {
      access_token: response.data.access_token!,
      refresh_token: response.data.refresh_token!,
      expires_in: response.data.expires_in!,
      token_type: response.data.token_type || 'bearer'
    };

    // Store tokens
    if (tokens.access_token && tokens.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_at: Date.now() + (tokens.expires_in * 1000)
      });
    }

    // Call onSignIn callback if it exists
    if (this.onSignIn) {
      this.onSignIn({ user: response.data.user });
    }

    return {
      user: response.data.user,
      tokens: {
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_in: tokens.expires_in,
        token_type: tokens.token_type
      }
    };
  }

  /**
   * Sign in user with email/username and password
   */
  async signIn(request: SignInRequest): Promise<AuthResponse> {
    // Validate input
    if (!request.email && !request.username) {
      throw new ValidationError('Either email or username must be provided');
    }

    if (request.email && !ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    if (request.username && !ValidationUtils.isValidUsername(request.username)) {
      throw new ValidationError('Invalid username format');
    }

    const response = await this.http.post<AuthApiResponse>('/api/v1/auth/login', request);

    // Handle MFA requirement. The API (apps/api/app/routers/v1/auth.py:451-452)
    // returns `mfa_required: true` + `mfa_token` and NO tokens when the user has
    // a second factor. Surface that to the caller so it can render a code-entry
    // step and call verifyMfaChallenge(). The prior check looked for a
    // non-existent `requires_mfa` key, so this branch never fired and the code
    // fell through to build an AuthResponse whose token fields were all
    // undefined — silently "swallowing" the challenge.
    if (response.data.mfa_required) {
      return {
        user: response.data.user,
        mfa_required: true,
        mfa_token: response.data.mfa_token,
      };
    }

    // Extract tokens - support both nested (API actual) and flat (legacy) structures
    const tokens = response.data.tokens || {
      access_token: response.data.access_token!,
      refresh_token: response.data.refresh_token!,
      expires_in: response.data.expires_in!,
      token_type: response.data.token_type || 'bearer'
    };

    // Store tokens
    if (tokens.access_token && tokens.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_at: Date.now() + (tokens.expires_in * 1000)
      });
    }

    // Call onSignIn callback if it exists
    if (this.onSignIn) {
      this.onSignIn({ user: response.data.user });
    }

    return {
      user: response.data.user,
      tokens: {
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_in: tokens.expires_in,
        token_type: tokens.token_type
      }
    };
  }

  /**
   * Complete an MFA challenge during sign-in.
   *
   * After {@link signIn} returns `{ mfa_required: true, mfa_token }`, call this
   * with the same `mfa_token` and the user's 6-digit TOTP code (or a formatted
   * backup code, e.g. `ABCD-1234`) to obtain real session tokens. On success the
   * tokens are persisted and the onSignIn callback fires, exactly as a normal
   * sign-in would.
   *
   * Targets `POST /api/v1/mfa/challenge/verify`
   * (apps/api/app/routers/v1/mfa.py:565), which returns the same
   * `SignInResponse` shape as sign-in: `{ user, tokens: { access_token,
   * refresh_token, expires_in, token_type } }`.
   */
  async verifyMfaChallenge(mfaToken: string, code: string): Promise<AuthResponse> {
    if (!mfaToken) {
      throw new ValidationError('mfa_token is required to complete the MFA challenge');
    }
    // Server accepts a 6-digit TOTP code or an 8-char backup code (with or
    // without the XXXX-XXXX dash). Keep validation permissive but non-empty.
    if (!code || !code.trim()) {
      throw new ValidationError('An MFA code is required');
    }

    const response = await this.http.post<AuthApiResponse>(
      '/api/v1/mfa/challenge/verify',
      { mfa_token: mfaToken, code: code.trim() },
      { skipAuth: true }
    );

    // The challenge-verify endpoint returns tokens nested under `tokens`
    // (SignInResponse). Support the flat shape too for resilience.
    const tokens = response.data.tokens || {
      access_token: response.data.access_token!,
      refresh_token: response.data.refresh_token!,
      expires_in: response.data.expires_in!,
      token_type: response.data.token_type || 'bearer'
    };

    if (tokens.access_token && tokens.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_at: Date.now() + (tokens.expires_in * 1000)
      });
    }

    if (this.onSignIn) {
      this.onSignIn({ user: response.data.user });
    }

    return {
      user: response.data.user,
      tokens: {
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_in: tokens.expires_in,
        token_type: tokens.token_type
      }
    };
  }

  /**
   * Sign out current user
   */
  async signOut(): Promise<void> {
    try {
      const refreshToken = await this.tokenManager.getRefreshToken();
      await this.http.post('/api/v1/auth/logout', { refresh_token: refreshToken });
    } catch {
      // Continue with sign out even if API call fails
    } finally {
      await this.tokenManager.clearTokens();
      // Call onSignOut callback if it exists
      if (this.onSignOut) {
        this.onSignOut();
      }
    }
  }

  /**
   * Refresh access token
   */
  async refreshToken(request?: RefreshTokenRequest): Promise<TokenResponse> {
    // If no request provided, get refresh token from tokenManager
    if (!request) {
      const refreshToken = await this.tokenManager.getRefreshToken();
      if (!refreshToken) {
        throw new AuthenticationError('No refresh token available');
      }
      request = { refresh_token: refreshToken };
    }

    const response = await this.http.post<TokenResponse>('/api/v1/auth/refresh', request, {
      skipAuth: true
    });

    // Store new tokens
    if (response.data.access_token && response.data.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: Date.now() + ((response.data as any).expires_in * 1000)
      });
      // Direct and scheduled refreshes bypass the HTTP client's 401 recovery.
      // Publish through its existing forwarding path only after persistence.
      this.http.emit('token:refreshed', { tokens: response.data });
    }

    return {
      access_token: response.data.access_token,
      refresh_token: response.data.refresh_token,
      expires_in: response.data.expires_in,
      token_type: response.data.token_type
    };
  }

  /**
   * Get current user information
   */
  async getCurrentUser(): Promise<User | null> {
    try {
      const response = await this.http.get<User>('/api/v1/auth/me');
      return response.data;
    } catch (error) {
      if (error instanceof AuthenticationError) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Update user profile
   */
  async updateProfile(updates: UserUpdateRequest): Promise<User> {
    const response = await this.http.patch<User>('/api/v1/auth/profile', updates);
    return response.data;
  }

  /**
   * Request password reset email
   */
  async forgotPassword(request: ForgotPasswordRequest): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/password/forgot', request, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Request password reset email
   */
  async requestPasswordReset(email: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/password/reset-request', {
      email
    }, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Reset password with token
   */
  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const passwordValidation = ValidationUtils.validatePassword(newPassword);
    if (!passwordValidation.isValid) {
      throw new ValidationError('Password validation failed',
        passwordValidation.errors.map(err => ({ field: 'password', message: err }))
      );
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/password/confirm', {
      token,
      password: newPassword
    }, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Change password for authenticated user
   */
  async changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
    const passwordValidation = ValidationUtils.validatePassword(newPassword);
    if (!passwordValidation.isValid) {
      throw new ValidationError('Password validation failed',
        passwordValidation.errors.map(err => ({ field: 'password', message: err }))
      );
    }

    const response = await this.http.put<{ message: string }>('/api/v1/auth/password/change', {
      current_password: currentPassword,
      new_password: newPassword
    });
    return response.data;
  }

  /**
   * Verify email with token
   */
  async verifyEmail(token: string): Promise<{ message: string }> {
    const response = await this.http.post<{ message: string }>('/api/v1/auth/email/verify', {
      token
    }, { skipAuth: true });
    return response.data;
  }

  /**
   * Resend email verification
   */
  async resendVerificationEmail(): Promise<{ message: string }> {
    const response = await this.http.post<{ message: string }>('/api/v1/auth/email/resend-verification');
    return response.data;
  }

  /**
   * Send magic link for passwordless authentication
   */
  async sendMagicLink(request: MagicLinkRequest): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/magic-link', request, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Resend magic link
   */
  async resendMagicLink(email: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/magic-link/resend', {
      email
    }, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Verify magic link token and sign in
   */
  async verifyMagicLink(token: string): Promise<AuthResponse> {
    const response = await this.http.post<AuthResponse>('/api/v1/auth/magic-link/verify', {
      token
    }, { skipAuth: true });

    // Store tokens
    if (response.data.tokens && response.data.tokens.access_token && response.data.tokens.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.tokens.access_token,
        refresh_token: response.data.tokens.refresh_token,
        expires_at: Date.now() + (response.data.tokens.expires_in * 1000)
      });
    }

    // Call onSignIn callback if it exists
    if (this.onSignIn) {
      this.onSignIn({ user: response.data.user });
    }

    return response.data;
  }

  // MFA Operations

  /**
   * Get MFA status for current user
   */
  async getMFAStatus(): Promise<MFAStatusResponse> {
    const response = await this.http.get<MFAStatusResponse>('/api/v1/mfa/status');
    return response.data;
  }

  /**
   * Begin MFA enrollment for the signed-in user (returns TOTP secret, QR code,
   * provisioning URI, and one-time backup codes). Requires the user's password.
   *
   * Targets `POST /api/v1/mfa/enable` (apps/api/app/routers/v1/mfa.py:236),
   * whose body is `MFAEnableRequest = { password }`. The prior implementation
   * POSTed `{ method }` to `/api/v1/auth/mfa/enable` — both the path (that route
   * does not exist; the mfa router is mounted at `/mfa`, not `/auth/mfa`) and
   * the body were wrong, so enrollment always failed.
   */
  async enableMFA(password: string): Promise<MFAEnableResponse> {
    const response = await this.http.post<MFAEnableResponse>('/api/v1/mfa/enable', { password });
    return response.data;
  }

  /**
   * Verify MFA enrollment by confirming a TOTP code from the authenticator that
   * scanned the QR from {@link enableMFA}. This finalizes enrollment; it does NOT
   * issue session tokens (the user is already signed in during enrollment).
   *
   * Targets `POST /api/v1/mfa/verify` (apps/api/app/routers/v1/mfa.py:291),
   * which requires the caller to be authenticated and returns
   * `{ message: string }`. The prior code POSTed to `/api/v1/auth/mfa/verify`
   * (nonexistent path) and expected tokens back.
   *
   * NOTE: to complete a second factor during SIGN-IN, use
   * {@link verifyMfaChallenge} instead — that is the token-issuing path.
   */
  async verifyMFA(request: MFAVerifyRequest): Promise<{ message: string }> {
    if (!/^\d{6}$/.test(request.code)) {
      throw new ValidationError('MFA code must be 6 digits');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/mfa/verify', request);
    return response.data;
  }

  /**
   * Disable MFA for the signed-in user. Requires the account password.
   *
   * Targets `POST /api/v1/mfa/disable` (apps/api/app/routers/v1/mfa.py:321),
   * body `{ password }` (an optional `code` may also be supplied). The prior
   * code used the nonexistent `/api/v1/auth/mfa/disable` path.
   */
  async disableMFA(password: string, code?: string): Promise<{ message: string }> {
    const body: { password: string; code?: string } = { password };
    if (code) body.code = code;
    const response = await this.http.post<{ message: string }>('/api/v1/mfa/disable', body);
    return response.data;
  }

  /**
   * Regenerate the user's one-time MFA backup codes (invalidates the old set).
   * Requires the account password.
   *
   * Targets `POST /api/v1/mfa/regenerate-backup-codes`
   * (apps/api/app/routers/v1/mfa.py:363). IMPORTANT: that handler declares
   * `password: str` as a bare parameter, which FastAPI binds as a QUERY
   * parameter, not a JSON body field. The prior code sent `{ password }` in the
   * request body, so the server saw no password and rejected the call — hence
   * `password` is passed via `params` here.
   */
  async regenerateMFABackupCodes(password: string): Promise<MFABackupCodesResponse> {
    const response = await this.http.post<MFABackupCodesResponse>(
      '/api/v1/mfa/regenerate-backup-codes',
      undefined,
      { params: { password } }
    );
    return response.data;
  }

  /**
   * Validate MFA code (for testing)
   */
  async validateMFACode(code: string): Promise<{ valid: boolean; message: string }> {
    if (!/^\d{6}$/.test(code) && !/^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(code)) {
      throw new ValidationError('Invalid MFA code format');
    }

    // The handler (apps/api/app/routers/v1/mfa.py:400) declares `code: str` as a
    // bare parameter → FastAPI binds it as a QUERY parameter, so it is sent via
    // `params`, not the JSON body (which the server would ignore).
    const response = await this.http.post<{ valid: boolean; message: string }>(
      '/api/v1/mfa/validate-code',
      undefined,
      { params: { code } }
    );
    return response.data;
  }

  /**
   * Get MFA recovery options
   */
  async getMFARecoveryOptions(email: string): Promise<{
    recovery_available: boolean;
    methods: {
      backup_codes: boolean;
      email_recovery: boolean;
    };
  }> {
    if (!ValidationUtils.isValidEmail(email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.get(`/api/v1/mfa/recovery-options?email=${encodeURIComponent(email)}`, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Initiate MFA recovery
   */
  async initiateMFARecovery(email: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/mfa/initiate-recovery', {
      email
    }, { skipAuth: true });
    return response.data;
  }

  // OAuth Operations

  /**
   * Get available OAuth providers
   */
  async getOAuthProviders(): Promise<Array<{ provider?: string; name: string; enabled: boolean }>> {
    const response = await this.http.get<OAuthProvidersResponse>('/api/v1/auth/oauth/providers', {
      skipAuth: true
    });
    return response.data.providers;
  }

  /**
   * Initiate OAuth authorization flow
   */
  /**
   * Sign in with OAuth provider
   */
  async signInWithOAuth(params: { provider: string; redirect_uri: string }): Promise<{
    authorization_url: string;
  }> {
    const response = await this.http.get('/api/v1/auth/oauth/authorize', {
      params
    });
    return response.data;
  }

  async initiateOAuth(
    provider: OAuthProvider,
    options?: {
      redirect_uri?: string;
      redirect_to?: string;
      scopes?: string[];
    }
  ): Promise<{
    authorization_url: string;
    state: string;
    provider: string;
  }> {
    const params: Record<string, any> = {};

    if (options?.redirect_uri) {
      params.redirect_uri = options.redirect_uri;
    }
    if (options?.redirect_to) {
      params.redirect_to = options.redirect_to;
    }
    if (options?.scopes) {
      params.scopes = options.scopes.join(',');
    }

    const response = await this.http.post<{ authorization_url: string; state: string; provider: string }>(`/api/v1/auth/oauth/authorize/${provider}`, null, {
      params,
      skipAuth: true
    });
    return response.data;
  }

  // ---------------------------------------------------------------------------
  // "Sign in with Janua" — OIDC PROVIDER flow
  //
  // These target Janua's own OIDC authorization server
  // (`/api/v1/oauth/authorize` + `/api/v1/oauth/token`), used when an app in the
  // MADFAM ecosystem treats Janua as its identity provider. This is DISTINCT
  // from the social `initiateOAuth(...)` methods above, which federate external
  // IdPs (Google/GitHub/…). `janua` is NOT a valid social `OAuthProvider`, so it
  // must never be routed through those methods.
  // ---------------------------------------------------------------------------

  /**
   * Build the Janua OIDC authorization URL with PKCE, persisting the
   * `code_verifier` + `state` in sessionStorage for the callback exchange.
   *
   * Use this when you want to control the redirect yourself (e.g. render a link
   * or open a popup). Most callers want {@link initiateJanuaSSO}.
   */
  async getJanuaAuthorizeUrl(options: JanuaSSOOptions): Promise<JanuaAuthorizeUrlResult> {
    if (!options?.clientId) {
      throw new ValidationError('januaClientId (clientId) is required for Sign in with Janua');
    }
    if (!options.redirectUri) {
      throw new ValidationError('redirectUri is required for Sign in with Janua');
    }

    const baseURL = options.baseUrl || this.baseUrl;
    if (!baseURL) {
      throw new ValidationError(
        'A Janua base URL is required (configure the SDK client baseURL or pass baseUrl)'
      );
    }

    const codeVerifier = generateCodeVerifier();
    const codeChallenge = await generateCodeChallenge(codeVerifier);
    const state = options.state || generateState();

    // Persist verifier + state so the callback (possibly on another page load)
    // can validate state and complete the PKCE exchange.
    storePKCEParams(codeVerifier, state);

    const scopes = (options.scopes && options.scopes.length > 0)
      ? options.scopes.join(' ')
      : 'openid profile email';

    const url = buildJanuaAuthorizeUrl({
      baseURL,
      clientId: options.clientId,
      redirectUri: options.redirectUri,
      codeChallenge,
      state,
      scopes,
      nonce: options.nonce,
      prompt: options.prompt,
    });

    return { url, state, codeVerifier };
  }

  /**
   * Begin the "Sign in with Janua" OIDC flow by redirecting the browser to
   * Janua's authorization endpoint. Requires a browser environment.
   */
  async initiateJanuaSSO(options: JanuaSSOOptions): Promise<void> {
    const { url } = await this.getJanuaAuthorizeUrl(options);

    if (typeof window === 'undefined' || !window.location) {
      throw new AuthenticationError(
        'initiateJanuaSSO requires a browser environment; use getJanuaAuthorizeUrl on the server'
      );
    }
    window.location.href = url;
  }

  /**
   * Complete the "Sign in with Janua" OIDC flow: validate `state`, exchange the
   * authorization `code` (with the stored PKCE `code_verifier`) at
   * `POST /api/v1/oauth/token`, and store the resulting tokens.
   *
   * The token endpoint is a standard OAuth 2.0 endpoint that consumes
   * `application/x-www-form-urlencoded`, so this uses a direct form POST rather
   * than the JSON HTTP client. Intended for public clients (no client secret) —
   * confidential clients must exchange the code server-side.
   */
  async handleJanuaSSOCallback(
    code: string,
    state: string,
    options: {
      clientId: string;
      redirectUri: string;
      /** Explicit PKCE verifier; falls back to the persisted one when omitted. */
      codeVerifier?: string;
      /** Override the Janua base URL (defaults to the client's configured baseURL). */
      baseUrl?: string;
    }
  ): Promise<JanuaSSOTokenResponse> {
    if (!code) {
      throw new ValidationError('Authorization code is required');
    }
    if (!options?.clientId || !options.redirectUri) {
      throw new ValidationError('clientId and redirectUri are required to complete Sign in with Janua');
    }

    // CSRF: the returned state must match what we stored at initiation.
    if (!validateState(state)) {
      throw new AuthenticationError('Invalid OAuth state — possible CSRF, aborting token exchange');
    }

    const codeVerifier = options.codeVerifier || retrievePKCEParams()?.verifier;
    if (!codeVerifier) {
      throw new AuthenticationError('Missing PKCE code_verifier for token exchange');
    }

    const baseURL = stripTrailingSlashes(options.baseUrl || this.baseUrl);
    if (!baseURL) {
      throw new ValidationError(
        'A Janua base URL is required (configure the SDK client baseURL or pass baseUrl)'
      );
    }

    const body = new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      redirect_uri: options.redirectUri,
      client_id: options.clientId,
      code_verifier: codeVerifier,
    });

    const response = await fetch(`${baseURL}/api/v1/oauth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });

    if (!response.ok) {
      let detail = `Token exchange failed (${response.status})`;
      try {
        const errData = await response.json();
        detail = errData?.detail || errData?.error_description || errData?.error || detail;
      } catch {
        // non-JSON error body; keep the status-based message
      }
      clearPKCEParams();
      throw new AuthenticationError(detail);
    }

    const tokens = (await response.json()) as JanuaSSOTokenResponse;

    // One-time material — clear it as soon as the exchange succeeds.
    clearPKCEParams();

    if (tokens.access_token && tokens.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_at: Date.now() + (tokens.expires_in * 1000),
      });
    }

    if (this.onSignIn) {
      this.onSignIn();
    }

    return tokens;
  }

  /**
   * Handle OAuth callback
   */
  async handleOAuthCallback(code: string, state: string): Promise<AuthResponse> {
    const response = await this.http.post<AuthApiResponse>('/api/v1/auth/oauth/callback', {
      code,
      state
    }, {
      skipAuth: true
    });

    // Extract tokens - support both nested (API actual) and flat (legacy) structures
    const tokens = response.data.tokens || {
      access_token: response.data.access_token!,
      refresh_token: response.data.refresh_token!,
      expires_in: response.data.expires_in!,
      token_type: response.data.token_type || 'bearer'
    };

    // Store tokens
    if (tokens.access_token && tokens.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_at: Date.now() + (tokens.expires_in * 1000)
      });
    }

    // Call onSignIn callback if it exists
    if (this.onSignIn) {
      this.onSignIn({ user: response.data.user });
    }

    return {
      user: response.data.user,
      tokens: {
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_in: tokens.expires_in,
        token_type: tokens.token_type
      }
    };
  }

  /**
   * Handle OAuth callback (with provider - for advanced use)
   */
  async handleOAuthCallbackWithProvider(
    provider: OAuthProvider,
    code: string,
    state: string
  ): Promise<{
    access_token?: string;
    refresh_token?: string;
    token_type?: string;
    expires_in?: number;
    user?: User;
    is_new_user?: boolean;
    status?: string;
    redirect_url?: string;
  }> {
    const response = await this.http.get(`/api/v1/auth/oauth/callback/${provider}`, {
      params: { code, state },
      skipAuth: true
    });

    // Extract tokens - support both nested (API actual) and flat (legacy) structures
    const accessToken = response.data.tokens?.access_token || response.data.access_token;
    const refreshToken = response.data.tokens?.refresh_token || response.data.refresh_token;
    const expiresIn = response.data.tokens?.expires_in || response.data.expires_in;

    // Store tokens if present
    if (accessToken && refreshToken) {
      await this.tokenManager.setTokens({
        access_token: accessToken,
        refresh_token: refreshToken,
        expires_at: Date.now() + (expiresIn * 1000)
      });
    }

    // Call onSignIn callback if user is present
    if (this.onSignIn && response.data.user) {
      this.onSignIn({ user: response.data.user });
    }

    return response.data;
  }

  /**
   * Link OAuth account to current user
   */
  async linkOAuthAccount(
    provider: OAuthProvider,
    options?: {
      redirect_uri?: string;
    }
  ): Promise<{
    authorization_url: string;
    state: string;
    provider: string;
    action: string;
  }> {
    const params: Record<string, string> = {};

    if (options?.redirect_uri) {
      params.redirect_uri = options.redirect_uri;
    }

    const response = await this.http.post<{ authorization_url: string; state: string; provider: string; action: string }>(`/api/v1/auth/oauth/link/${provider}`, null, {
      params
    });
    return response.data;
  }

  /**
   * Unlink OAuth account from current user
   */
  async unlinkOAuthAccount(provider: OAuthProvider): Promise<{
    message: string;
    provider: string;
  }> {
    const response = await this.http.delete<{ message: string; provider: string }>(`/api/v1/auth/oauth/unlink/${provider}`);
    return response.data;
  }

  /**
   * Get linked OAuth accounts for current user
   */
  async getLinkedAccounts(): Promise<LinkedAccountsResponse> {
    const response = await this.http.get<LinkedAccountsResponse>('/api/v1/auth/oauth/accounts');
    return response.data;
  }

  // Passkey Operations

  /**
   * Check WebAuthn availability
   */
  async checkPasskeyAvailability(): Promise<{
    available: boolean;
    platform_authenticator: boolean;
    roaming_authenticator: boolean;
    conditional_mediation: boolean;
    user_verifying_platform_authenticator: boolean;
  }> {
    const response = await this.http.get('/api/v1/passkeys/availability', {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Get passkey registration options
   */
  async getPasskeyRegistrationOptions(options?: {
    name?: string;
    authenticator_attachment?: 'platform' | 'cross-platform';
  }): Promise<{
    challenge: string;
    rp: { id: string; name: string };
    user: { id: string; name: string; displayName: string };
    pubKeyCredParams: Array<{ type: string; alg: number }>;
    timeout: number;
    excludeCredentials: Array<{ id: string; type: string }>;
    authenticatorSelection: {
      authenticatorAttachment?: 'platform' | 'cross-platform';
      residentKey?: 'discouraged' | 'preferred' | 'required';
      requireResidentKey?: boolean;
      userVerification?: 'required' | 'preferred' | 'discouraged';
    };
    attestation: string;
  }> {
    type PasskeyRegisterOptions = {
      challenge: string;
      rp: { id: string; name: string };
      user: { id: string; name: string; displayName: string };
      pubKeyCredParams: Array<{ type: string; alg: number }>;
      timeout: number;
      excludeCredentials: Array<{ id: string; type: string }>;
      authenticatorSelection: {
        authenticatorAttachment?: 'platform' | 'cross-platform';
        residentKey?: 'discouraged' | 'preferred' | 'required';
        requireResidentKey?: boolean;
        userVerification?: 'required' | 'preferred' | 'discouraged';
      };
      attestation: string;
    };
    const response = await this.http.post<PasskeyRegisterOptions>('/api/v1/passkeys/register/options', options || {});
    return response.data;
  }

  /**
   * Verify passkey registration
   */
  async verifyPasskeyRegistration(
    credential: PublicKeyCredentialJSON,
    name?: string
  ): Promise<{
    verified: boolean;
    passkey_id: string;
    message: string;
  }> {
    const response = await this.http.post<{ verified: boolean; passkey_id: string; message: string }>('/api/v1/passkeys/register/verify', {
      credential,
      name
    });
    return response.data;
  }

  /**
   * Get passkey authentication (assertion) options to feed
   * `navigator.credentials.get`.
   *
   * Targets `POST /api/v1/passkeys/authenticate/options`
   * (apps/api/app/routers/v1/passkeys.py:291), body `{ email? }`. The response
   * includes a server-minted `sessionId` (passkeys.py:336) that keys the
   * one-time challenge stored in Redis. That `sessionId` MUST be passed back to
   * {@link verifyPasskeyAuthentication} — the verify endpoint reads the challenge
   * server-side by session id and never trusts a client-supplied challenge
   * (2026-08-23 replay-hardening fix).
   */
  async getPasskeyAuthenticationOptions(email?: string): Promise<{
    sessionId: string;
    challenge: string;
    rpId: string;
    timeout: number;
    allowCredentials: Array<{ id: string; type: string }>;
    userVerification: string;
  }> {
    type PasskeyAuthOptions = {
      sessionId: string;
      challenge: string;
      rpId: string;
      timeout: number;
      allowCredentials: Array<{ id: string; type: string }>;
      userVerification: string;
    };
    const data = email ? { email } : {};
    const response = await this.http.post<PasskeyAuthOptions>('/api/v1/passkeys/authenticate/options', data, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Verify a passkey assertion and sign the user in.
   *
   * Targets `POST /api/v1/passkeys/authenticate/verify`
   * (apps/api/app/routers/v1/passkeys.py:350). The handler takes the JSON body
   * `{ email?, credential }` AND a `session_id` QUERY parameter (a bare `str`
   * param, so it is not a body field). The server resolves the one-time
   * challenge from Redis by that session id.
   *
   * The response is FLAT — `{ verified, access_token, refresh_token, token_type,
   * expires_in, user }` (passkeys.py:472) — NOT nested under `tokens`. The prior
   * code sent `challenge` in the body (ignored by the new endpoint) and read
   * tokens from a nonexistent `response.data.tokens`, so it neither authenticated
   * nor stored tokens.
   */
  async verifyPasskeyAuthentication(
    credential: PublicKeyCredentialJSON,
    sessionId: string,
    email?: string
  ): Promise<{
    verified: boolean;
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
    user: Pick<User, 'id' | 'email' | 'first_name' | 'last_name'>;
  }> {
    type PasskeyAuthResponse = {
      verified: boolean;
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
      user: Pick<User, 'id' | 'email' | 'first_name' | 'last_name'>;
    };
    const response = await this.http.post<PasskeyAuthResponse>(
      '/api/v1/passkeys/authenticate/verify',
      { credential, email },
      { skipAuth: true, params: { session_id: sessionId } }
    );

    // Tokens are flat at the top level of the response.
    if (response.data.access_token && response.data.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: Date.now() + (response.data.expires_in * 1000)
      });
    }

    // Call onSignIn callback if it exists
    if (this.onSignIn) {
      this.onSignIn({ user: response.data.user as unknown as User });
    }

    return response.data;
  }

  /**
   * List user's passkeys
   */
  async listPasskeys(): Promise<Passkey[]> {
    const response = await this.http.get<Passkey[]>('/api/v1/passkeys/');
    return response.data;
  }

  /**
   * Update passkey name
   */
  async updatePasskey(passkeyId: string, name: string): Promise<Passkey> {
    if (!ValidationUtils.isValidUuid(passkeyId)) {
      throw new ValidationError('Invalid passkey ID format');
    }

    const response = await this.http.patch<Passkey>(`/api/v1/passkeys/${passkeyId}`, {
      name
    });
    return response.data;
  }

  /**
   * Delete passkey
   */
  async deletePasskey(passkeyId: string, password: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUuid(passkeyId)) {
      throw new ValidationError('Invalid passkey ID format');
    }

    const response = await this.http.delete<{ message: string }>(`/api/v1/passkeys/${passkeyId}`, {
      data: { password }
    });
    return response.data;
  }

  /**
   * Regenerate passkey secret
   */
  async regeneratePasskeySecret(passkeyId: string): Promise<Passkey> {
    if (!ValidationUtils.isValidUuid(passkeyId)) {
      throw new ValidationError('Invalid passkey ID format');
    }

    const response = await this.http.post<Passkey>(`/api/v1/passkeys/${passkeyId}/regenerate-secret`);
    return response.data;
  }
}
