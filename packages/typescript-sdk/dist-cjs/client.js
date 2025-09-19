"use strict";
/**
 * Main Plinto SDK client
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.createClient = exports.PlintoClient = void 0;
const http_client_1 = require("./http-client");
const utils_1 = require("./utils");
const errors_1 = require("./errors");
const auth_1 = require("./auth");
const users_1 = require("./users");
const sessions_1 = require("./sessions");
const organizations_1 = require("./organizations");
const webhooks_1 = require("./webhooks");
const admin_1 = require("./admin");
const enterprise_1 = require("./enterprise");
/**
 * Main Plinto SDK client class
 */
class PlintoClient extends utils_1.EventEmitter {
    constructor(config = {}) {
        super();
        // Validate and merge configuration
        this.config = this.validateAndMergeConfig(config);
        // Initialize token manager
        this.tokenManager = this.createTokenManager();
        // Initialize HTTP client
        this.httpClient = this.createHttpClient();
        // Initialize enterprise features
        this.enterprise = new enterprise_1.EnterpriseFeatures({
            licenseKey: config.licenseKey,
            apiUrl: this.config.baseURL
        });
        // Initialize modules
        this.auth = new auth_1.Auth(this.httpClient, this.tokenManager, () => this.emit('auth:signIn', {}), () => this.emit('auth:signOut', {}));
        this.users = new users_1.Users(this.httpClient);
        this.sessions = new sessions_1.Sessions(this.httpClient);
        this.organizations = new organizations_1.Organizations(this.httpClient);
        this.webhooks = new webhooks_1.Webhooks(this.httpClient);
        this.admin = new admin_1.Admin(this.httpClient);
        // Set up event forwarding
        this.setupEventForwarding();
        // Validate license on initialization if provided
        if (config.licenseKey) {
            this.validateLicense().catch(console.warn);
        }
        // Auto-refresh tokens if enabled
        if (this.config.autoRefreshTokens) {
            this.setupAutoTokenRefresh();
        }
    }
    /**
     * Validate and merge configuration with defaults
     */
    validateAndMergeConfig(config) {
        // Validate required configuration
        if (!config.baseURL) {
            throw new errors_1.ConfigurationError('baseURL is required');
        }
        // Set defaults
        const defaults = {
            baseURL: '',
            apiKey: undefined,
            timeout: 30000,
            retryAttempts: 3,
            retryDelay: 1000,
            environment: utils_1.EnvUtils.isBrowser() ? 'browser' : 'node',
            debug: false,
            autoRefreshTokens: true,
            tokenStorage: 'localStorage',
            customStorage: undefined
        };
        const mergedConfig = { ...defaults, ...config };
        // Validate baseURL format
        try {
            new URL(mergedConfig.baseURL);
        }
        catch {
            throw new errors_1.ConfigurationError('Invalid baseURL format');
        }
        // Validate timeout
        if (mergedConfig.timeout <= 0) {
            throw new errors_1.ConfigurationError('Timeout must be greater than 0');
        }
        // Validate retry attempts
        if (mergedConfig.retryAttempts < 0) {
            throw new errors_1.ConfigurationError('Retry attempts must be non-negative');
        }
        // Validate retry delay
        if (mergedConfig.retryDelay <= 0) {
            throw new errors_1.ConfigurationError('Retry delay must be greater than 0');
        }
        return mergedConfig;
    }
    /**
     * Create token manager instance
     */
    createTokenManager() {
        let storage;
        if (this.config.customStorage) {
            storage = this.config.customStorage;
        }
        else {
            storage = utils_1.EnvUtils.getDefaultStorage();
        }
        return new utils_1.TokenManager(storage);
    }
    /**
     * Create HTTP client instance
     */
    createHttpClient() {
        return (0, http_client_1.createHttpClient)(this.config, this.tokenManager);
    }
    /**
     * Set up event forwarding from HTTP client
     */
    setupEventForwarding() {
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
    setupAutoTokenRefresh() {
        const checkAndRefresh = async () => {
            try {
                const tokenData = await this.tokenManager.getTokenData();
                if (!tokenData)
                    return;
                // Check if token expires within 5 minutes
                const expiresIn = tokenData.expires_at - Date.now();
                const fiveMinutes = 5 * 60 * 1000;
                if (expiresIn <= fiveMinutes && expiresIn > 0) {
                    await this.auth.refreshToken({ refresh_token: tokenData.refresh_token });
                }
            }
            catch (error) {
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
    async isAuthenticated() {
        return await this.tokenManager.hasValidTokens();
    }
    /**
     * Get current access token
     */
    async getAccessToken() {
        return await this.tokenManager.getAccessToken();
    }
    /**
     * Get current refresh token
     */
    async getRefreshToken() {
        return await this.tokenManager.getRefreshToken();
    }
    /**
     * Set tokens (useful for SSO or external authentication)
     */
    async setTokens(tokens) {
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
    async signOut() {
        try {
            // Try to sign out from server
            await this.auth.signOut();
        }
        catch {
            // Ignore server errors during sign out
        }
        finally {
            // Always clear local tokens
            await this.tokenManager.clearTokens();
            this.emit('auth:signedOut', {});
        }
    }
    /**
     * Get current user (if authenticated)
     */
    async getCurrentUser() {
        try {
            if (await this.isAuthenticated()) {
                return await this.auth.getCurrentUser();
            }
            return null;
        }
        catch {
            return null;
        }
    }
    // Configuration Methods
    /**
     * Update configuration
     */
    updateConfig(updates) {
        this.config = this.validateAndMergeConfig({ ...this.config, ...updates });
    }
    /**
     * Get current configuration
     */
    getConfig() {
        return { ...this.config };
    }
    /**
     * Enable debug mode
     */
    enableDebug() {
        this.config.debug = true;
    }
    /**
     * Disable debug mode
     */
    disableDebug() {
        this.config.debug = false;
    }
    // Enterprise Methods
    /**
     * Set or update license key
     */
    setLicenseKey(key) {
        this.enterprise.setLicenseKey(key);
        this.licenseInfo = undefined;
    }
    /**
     * Validate current license
     */
    async validateLicense() {
        this.licenseInfo = await this.enterprise.validateLicense();
        return this.licenseInfo;
    }
    /**
     * Get current license info
     */
    getLicenseInfo() {
        return this.licenseInfo;
    }
    /**
     * Check if a feature is available
     */
    async hasFeature(feature) {
        const featureKey = typeof feature === 'string' && feature in enterprise_1.FEATURES
            ? enterprise_1.FEATURES[feature]
            : feature;
        return await this.enterprise.hasFeature(featureKey);
    }
    /**
     * Enable SSO (Enterprise feature)
     */
    async enableSSO(type, config) {
        const featureKey = type === 'saml' ? enterprise_1.FEATURES.SSO_SAML : enterprise_1.FEATURES.SSO_OIDC;
        await this.enterprise.requireEnterprise(featureKey);
        return await this.httpClient.post('/v1/enterprise/sso/configure', {
            type,
            config
        });
    }
    /**
     * Get audit logs (Enterprise feature)
     */
    async getAuditLogs(params) {
        await this.enterprise.requireEnterprise(enterprise_1.FEATURES.AUDIT_LOGS);
        return await this.httpClient.get('/v1/enterprise/audit-logs', { params });
    }
    /**
     * Create custom role (Enterprise feature)
     */
    async createCustomRole(role) {
        await this.enterprise.requireEnterprise(enterprise_1.FEATURES.CUSTOM_ROLES);
        return await this.httpClient.post('/v1/enterprise/roles', role);
    }
    /**
     * Enable white labeling (Enterprise feature)
     */
    async configureWhiteLabeling(config) {
        await this.enterprise.requireEnterprise(enterprise_1.FEATURES.WHITE_LABELING);
        return await this.httpClient.post('/v1/enterprise/white-label', config);
    }
    /**
     * Get compliance reports (Enterprise feature)
     */
    async getComplianceReport(type) {
        await this.enterprise.requireEnterprise(enterprise_1.FEATURES.COMPLIANCE_REPORTS);
        return await this.httpClient.get(`/v1/enterprise/compliance/${type}`);
    }
    /**
     * Check rate limits for current operation
     */
    async checkRateLimit(operation) {
        return await this.enterprise.checkRateLimit(operation);
    }
    // Event Methods (inherited from EventEmitter but with typed interface)
    /**
     * Add event listener
     */
    on(event, handler) {
        return super.on(event, handler);
    }
    /**
     * Add one-time event listener
     */
    once(event, handler) {
        return super.once(event, handler);
    }
    /**
     * Remove all listeners for an event
     */
    off(event) {
        super.removeAllListeners(event);
    }
    // Utility Methods
    /**
     * Test API connectivity
     */
    async testConnection() {
        const startTime = Date.now();
        try {
            await this.httpClient.get('/api/v1/auth/oauth/providers', { skipAuth: true });
            const latency = Math.max(1, Date.now() - startTime);
            return {
                success: true,
                latency
            };
        }
        catch (error) {
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
    getVersion() {
        return '1.0.0'; // This should be dynamically set during build
    }
    /**
     * Get SDK environment info
     */
    getEnvironmentInfo() {
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
    getUserAgent() {
        const version = this.getVersion();
        if (utils_1.EnvUtils.isBrowser()) {
            return `plinto-typescript-sdk/${version} (Browser)`;
        }
        else if (utils_1.EnvUtils.isNode()) {
            const nodeVersion = typeof process !== 'undefined' ? process.version : 'unknown';
            return `plinto-typescript-sdk/${version} (Node.js ${nodeVersion})`;
        }
        else {
            return `plinto-typescript-sdk/${version}`;
        }
    }
    // ===================================
    // Convenience methods for common operations
    // ===================================
    /**
     * Sign in a user (convenience method)
     */
    async signIn(request) {
        return this.auth.signIn(request);
    }
    /**
     * Sign up a new user (convenience method)
     */
    async signUp(request) {
        return this.auth.signUp(request);
    }
    /**
     * Sign in with passkey (convenience method)
     */
    async signInWithPasskey(email) {
        // This would integrate with WebAuthn API
        // For now, throw not implemented
        throw new Error('Passkey sign-in not yet implemented. Use auth.signIn() instead.');
    }
    /**
     * Update current user (convenience method)
     */
    async updateUser(request) {
        return this.users.updateCurrentUser(request);
    }
    /**
     * Sign out the current user (convenience method)
     */
    async signOut() {
        return this.auth.signOut();
    }
    /**
     * Get current user (convenience method)
     */
    async getCurrentUser() {
        try {
            return await this.users.getCurrentUser();
        }
        catch {
            return null;
        }
    }
    /**
     * Check if user is authenticated (convenience method)
     */
    isAuthenticated() {
        return this.tokenManager.hasValidToken();
    }
    /**
     * Get current access token (convenience method)
     */
    async getAccessToken() {
        const tokens = await this.tokenManager.getTokens();
        return tokens?.access_token || null;
    }
    /**
     * Get current refresh token (convenience method)
     */
    async getRefreshToken() {
        const tokens = await this.tokenManager.getTokens();
        return tokens?.refresh_token || null;
    }
    /**
     * Destroy the client and cleanup resources
     */
    destroy() {
        this.removeAllListeners();
        // Note: We don't clear tokens here as that would sign out the user
        // Use signOut() if you want to clear tokens
    }
}
exports.PlintoClient = PlintoClient;
/**
 * Create a new Plinto client instance
 */
function createClient(config = {}) {
    return new PlintoClient(config);
}
exports.createClient = createClient;
/**
 * Default export
 */
exports.default = PlintoClient;
//# sourceMappingURL=client.js.map