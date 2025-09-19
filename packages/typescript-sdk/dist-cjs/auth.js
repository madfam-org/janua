"use strict";
/**
 * Authentication module for the Plinto TypeScript SDK
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.Auth = void 0;
const errors_1 = require("./errors");
const utils_1 = require("./utils");
/**
 * Authentication operations
 */
class Auth {
    constructor(http, tokenManager, onSignIn, onSignOut) {
        this.http = http;
        this.tokenManager = tokenManager;
        this.onSignIn = onSignIn;
        this.onSignOut = onSignOut;
    }
    /**
     * Sign up a new user
     */
    async signUp(request) {
        // Validate input
        if (!utils_1.ValidationUtils.isValidEmail(request.email)) {
            throw new errors_1.ValidationError('Invalid email format');
        }
        const passwordValidation = utils_1.ValidationUtils.validatePassword(request.password);
        if (!passwordValidation.isValid) {
            throw new errors_1.ValidationError('Password validation failed', passwordValidation.errors.map(err => ({ field: 'password', message: err })));
        }
        if (request.username && !utils_1.ValidationUtils.isValidUsername(request.username)) {
            throw new errors_1.ValidationError('Invalid username format');
        }
        const response = await this.http.post('/api/v1/auth/register', request);
        // Store tokens
        if (response.data.access_token && response.data.refresh_token) {
            await this.tokenManager.setTokens({
                access_token: response.data.access_token,
                refresh_token: response.data.refresh_token,
                expires_at: Date.now() + (response.data.expires_in * 1000)
            });
        }
        // Call onSignIn callback if it exists
        if (this.onSignIn) {
            this.onSignIn({ user: response.data.user });
        }
        return {
            user: response.data.user,
            tokens: {
                access_token: response.data.access_token,
                refresh_token: response.data.refresh_token,
                expires_in: response.data.expires_in,
                token_type: response.data.token_type
            }
        };
    }
    /**
     * Sign in user with email/username and password
     */
    async signIn(request) {
        // Validate input
        if (!request.email && !request.username) {
            throw new errors_1.ValidationError('Either email or username must be provided');
        }
        if (request.email && !utils_1.ValidationUtils.isValidEmail(request.email)) {
            throw new errors_1.ValidationError('Invalid email format');
        }
        if (request.username && !utils_1.ValidationUtils.isValidUsername(request.username)) {
            throw new errors_1.ValidationError('Invalid username format');
        }
        const response = await this.http.post('/api/v1/auth/login', request);
        // Handle MFA requirement
        if ('requires_mfa' in response.data) {
            return response.data; // Return MFA challenge response
        }
        // Store tokens
        if (response.data.access_token && response.data.refresh_token) {
            await this.tokenManager.setTokens({
                access_token: response.data.access_token,
                refresh_token: response.data.refresh_token,
                expires_at: Date.now() + (response.data.expires_in * 1000)
            });
        }
        // Call onSignIn callback if it exists
        if (this.onSignIn) {
            this.onSignIn({ user: response.data.user });
        }
        return {
            user: response.data.user,
            tokens: {
                access_token: response.data.access_token,
                refresh_token: response.data.refresh_token,
                expires_in: response.data.expires_in,
                token_type: response.data.token_type
            }
        };
    }
    /**
     * Sign out current user
     */
    async signOut() {
        try {
            const refreshToken = await this.tokenManager.getRefreshToken();
            await this.http.post('/api/v1/auth/logout', { refresh_token: refreshToken });
        }
        catch {
            // Continue with sign out even if API call fails
        }
        finally {
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
    async refreshToken(request) {
        // If no request provided, get refresh token from tokenManager
        if (!request) {
            const refreshToken = await this.tokenManager.getRefreshToken();
            if (!refreshToken) {
                throw new errors_1.AuthenticationError('No refresh token available');
            }
            request = { refresh_token: refreshToken };
        }
        const response = await this.http.post('/api/v1/auth/refresh', request, {
            skipAuth: true
        });
        // Store new tokens
        if (response.data.access_token && response.data.refresh_token) {
            await this.tokenManager.setTokens({
                access_token: response.data.access_token,
                refresh_token: response.data.refresh_token,
                expires_at: Date.now() + (response.data.expires_in * 1000)
            });
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
    async getCurrentUser() {
        try {
            const response = await this.http.get('/api/v1/auth/me');
            return response.data;
        }
        catch (error) {
            if (error instanceof errors_1.AuthenticationError) {
                return null;
            }
            throw error;
        }
    }
    /**
     * Update user profile
     */
    async updateProfile(updates) {
        const response = await this.http.patch('/api/v1/auth/profile', updates);
        return response.data;
    }
    /**
     * Request password reset email
     */
    async forgotPassword(request) {
        if (!utils_1.ValidationUtils.isValidEmail(request.email)) {
            throw new errors_1.ValidationError('Invalid email format');
        }
        const response = await this.http.post('/api/v1/auth/password/forgot', request, {
            skipAuth: true
        });
        return response.data;
    }
    /**
     * Request password reset email
     */
    async requestPasswordReset(email) {
        if (!utils_1.ValidationUtils.isValidEmail(email)) {
            throw new errors_1.ValidationError('Invalid email format');
        }
        const response = await this.http.post('/api/v1/auth/password/reset-request', {
            email
        }, {
            skipAuth: true
        });
        return response.data;
    }
    /**
     * Reset password with token
     */
    async resetPassword(token, newPassword) {
        const passwordValidation = utils_1.ValidationUtils.validatePassword(newPassword);
        if (!passwordValidation.isValid) {
            throw new errors_1.ValidationError('Password validation failed', passwordValidation.errors.map(err => ({ field: 'password', message: err })));
        }
        const response = await this.http.post('/api/v1/auth/password/confirm', {
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
    async changePassword(currentPassword, newPassword) {
        const passwordValidation = utils_1.ValidationUtils.validatePassword(newPassword);
        if (!passwordValidation.isValid) {
            throw new errors_1.ValidationError('Password validation failed', passwordValidation.errors.map(err => ({ field: 'password', message: err })));
        }
        const response = await this.http.put('/api/v1/auth/password/change', {
            current_password: currentPassword,
            new_password: newPassword
        });
        return response.data;
    }
    /**
     * Verify email with token
     */
    async verifyEmail(token) {
        const response = await this.http.post('/api/v1/auth/email/verify', {
            token
        }, { skipAuth: true });
        return response.data;
    }
    /**
     * Resend email verification
     */
    async resendVerificationEmail() {
        const response = await this.http.post('/api/v1/auth/email/resend-verification');
        return response.data;
    }
    /**
     * Send magic link for passwordless authentication
     */
    async sendMagicLink(request) {
        if (!utils_1.ValidationUtils.isValidEmail(request.email)) {
            throw new errors_1.ValidationError('Invalid email format');
        }
        const response = await this.http.post('/api/v1/auth/magic-link', request, {
            skipAuth: true
        });
        return response.data;
    }
    /**
     * Resend magic link
     */
    async resendMagicLink(email) {
        if (!utils_1.ValidationUtils.isValidEmail(email)) {
            throw new errors_1.ValidationError('Invalid email format');
        }
        const response = await this.http.post('/api/v1/auth/magic-link/resend', {
            email
        }, {
            skipAuth: true
        });
        return response.data;
    }
    /**
     * Verify magic link token and sign in
     */
    async verifyMagicLink(token) {
        try {
            const response = await this.http.post('/api/v1/auth/magic-link/verify', {
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
        catch (error) {
            // Re-throw the error to let tests catch it
            throw error;
        }
    }
    // MFA Operations
    /**
     * Get MFA status for current user
     */
    async getMFAStatus() {
        const response = await this.http.get('/api/v1/mfa/status');
        return response.data;
    }
    /**
     * Enable MFA (returns QR code and backup codes)
     */
    async enableMFA(method) {
        const response = await this.http.post('/api/v1/auth/mfa/enable', { method });
        return response.data;
    }
    /**
     * Verify MFA setup with TOTP code
     */
    async verifyMFA(request) {
        if (!/^\d{6}$/.test(request.code)) {
            throw new errors_1.ValidationError('MFA code must be 6 digits');
        }
        const response = await this.http.post('/api/v1/auth/mfa/verify', request);
        // Store tokens
        if (response.data.access_token && response.data.refresh_token) {
            await this.tokenManager.setTokens({
                access_token: response.data.access_token,
                refresh_token: response.data.refresh_token,
                expires_at: Date.now() + (response.data.expires_in * 1000)
            });
        }
        // Call onSignIn callback if it exists
        if (this.onSignIn) {
            this.onSignIn({ user: response.data.user });
        }
        return {
            user: response.data.user,
            tokens: {
                access_token: response.data.access_token,
                refresh_token: response.data.refresh_token,
                expires_in: response.data.expires_in,
                token_type: response.data.token_type
            }
        };
    }
    /**
     * Disable MFA
     */
    async disableMFA(password) {
        const response = await this.http.post('/api/v1/auth/mfa/disable', { password });
        return response.data;
    }
    /**
     * Regenerate MFA backup codes
     */
    async regenerateMFABackupCodes(password) {
        const response = await this.http.post('/api/v1/mfa/regenerate-backup-codes', {
            password
        });
        return response.data;
    }
    /**
     * Validate MFA code (for testing)
     */
    async validateMFACode(code) {
        if (!/^\d{6}$/.test(code) && !/^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(code)) {
            throw new errors_1.ValidationError('Invalid MFA code format');
        }
        const response = await this.http.post('/api/v1/mfa/validate-code', {
            code
        });
        return response.data;
    }
    /**
     * Get MFA recovery options
     */
    async getMFARecoveryOptions(email) {
        if (!utils_1.ValidationUtils.isValidEmail(email)) {
            throw new errors_1.ValidationError('Invalid email format');
        }
        const response = await this.http.get(`/api/v1/mfa/recovery-options?email=${encodeURIComponent(email)}`, {
            skipAuth: true
        });
        return response.data;
    }
    /**
     * Initiate MFA recovery
     */
    async initiateMFARecovery(email) {
        if (!utils_1.ValidationUtils.isValidEmail(email)) {
            throw new errors_1.ValidationError('Invalid email format');
        }
        const response = await this.http.post('/api/v1/mfa/initiate-recovery', {
            email
        }, { skipAuth: true });
        return response.data;
    }
    // OAuth Operations
    /**
     * Get available OAuth providers
     */
    async getOAuthProviders() {
        const response = await this.http.get('/api/v1/auth/oauth/providers', {
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
    async signInWithOAuth(params) {
        const response = await this.http.get('/api/v1/auth/oauth/authorize', {
            params
        });
        return response.data;
    }
    async initiateOAuth(provider, options) {
        const params = {};
        if (options?.redirect_uri) {
            params.redirect_uri = options.redirect_uri;
        }
        if (options?.redirect_to) {
            params.redirect_to = options.redirect_to;
        }
        if (options?.scopes) {
            params.scopes = options.scopes.join(',');
        }
        const response = await this.http.post(`/api/v1/auth/oauth/authorize/${provider}`, null, {
            params,
            skipAuth: true
        });
        return response.data;
    }
    /**
     * Handle OAuth callback
     */
    async handleOAuthCallback(code, state) {
        const response = await this.http.post('/api/v1/auth/oauth/callback', {
            code,
            state
        }, {
            skipAuth: true
        });
        // Store tokens
        if (response.data.access_token && response.data.refresh_token) {
            await this.tokenManager.setTokens({
                access_token: response.data.access_token,
                refresh_token: response.data.refresh_token,
                expires_at: Date.now() + (response.data.expires_in * 1000)
            });
        }
        // Call onSignIn callback if it exists
        if (this.onSignIn) {
            this.onSignIn({ user: response.data.user });
        }
        return {
            user: response.data.user,
            tokens: {
                access_token: response.data.access_token,
                refresh_token: response.data.refresh_token,
                expires_in: response.data.expires_in,
                token_type: response.data.token_type
            }
        };
    }
    /**
     * Handle OAuth callback (with provider - for advanced use)
     */
    async handleOAuthCallbackWithProvider(provider, code, state) {
        const response = await this.http.get(`/api/v1/auth/oauth/callback/${provider}`, {
            params: { code, state },
            skipAuth: true
        });
        // Store tokens if present
        if (response.data.access_token && response.data.refresh_token) {
            await this.tokenManager.setTokens({
                access_token: response.data.access_token,
                refresh_token: response.data.refresh_token,
                expires_at: Date.now() + (response.data.expires_in * 1000)
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
    async linkOAuthAccount(provider, options) {
        const params = {};
        if (options?.redirect_uri) {
            params.redirect_uri = options.redirect_uri;
        }
        const response = await this.http.post(`/api/v1/auth/oauth/link/${provider}`, null, {
            params
        });
        return response.data;
    }
    /**
     * Unlink OAuth account from current user
     */
    async unlinkOAuthAccount(provider) {
        const response = await this.http.delete(`/api/v1/auth/oauth/unlink/${provider}`);
        return response.data;
    }
    /**
     * Get linked OAuth accounts for current user
     */
    async getLinkedAccounts() {
        const response = await this.http.get('/api/v1/auth/oauth/accounts');
        return response.data;
    }
    // Passkey Operations
    /**
     * Check WebAuthn availability
     */
    async checkPasskeyAvailability() {
        const response = await this.http.get('/api/v1/passkeys/availability', {
            skipAuth: true
        });
        return response.data;
    }
    /**
     * Get passkey registration options
     */
    async getPasskeyRegistrationOptions(options) {
        const response = await this.http.post('/api/v1/passkeys/register/options', options || {});
        return response.data;
    }
    /**
     * Verify passkey registration
     */
    async verifyPasskeyRegistration(credential, name) {
        const response = await this.http.post('/api/v1/passkeys/register/verify', {
            credential,
            name
        });
        return response.data;
    }
    /**
     * Get passkey authentication options
     */
    async getPasskeyAuthenticationOptions(email) {
        const data = email ? { email } : {};
        const response = await this.http.post('/api/v1/passkeys/authenticate/options', data, {
            skipAuth: true
        });
        return response.data;
    }
    /**
     * Verify passkey authentication
     */
    async verifyPasskeyAuthentication(credential, challenge, email) {
        const response = await this.http.post('/api/v1/passkeys/authenticate/verify', {
            credential,
            challenge,
            email
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
    /**
     * List user's passkeys
     */
    async listPasskeys() {
        const response = await this.http.get('/api/v1/passkeys/');
        return response.data;
    }
    /**
     * Update passkey name
     */
    async updatePasskey(passkeyId, name) {
        if (!utils_1.ValidationUtils.isValidUuid(passkeyId)) {
            throw new errors_1.ValidationError('Invalid passkey ID format');
        }
        const response = await this.http.patch(`/api/v1/passkeys/${passkeyId}`, {
            name
        });
        return response.data;
    }
    /**
     * Delete passkey
     */
    async deletePasskey(passkeyId, password) {
        if (!utils_1.ValidationUtils.isValidUuid(passkeyId)) {
            throw new errors_1.ValidationError('Invalid passkey ID format');
        }
        const response = await this.http.delete(`/api/v1/passkeys/${passkeyId}`, {
            data: { password }
        });
        return response.data;
    }
    /**
     * Regenerate passkey secret
     */
    async regeneratePasskeySecret(passkeyId) {
        if (!utils_1.ValidationUtils.isValidUuid(passkeyId)) {
            throw new errors_1.ValidationError('Invalid passkey ID format');
        }
        const response = await this.http.post(`/api/v1/passkeys/${passkeyId}/regenerate-secret`);
        return response.data;
    }
}
exports.Auth = Auth;
//# sourceMappingURL=auth.js.map