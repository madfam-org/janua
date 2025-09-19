"use strict";
/**
 * Session management module
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.Sessions = void 0;
/**
 * Sessions module for managing user sessions
 */
class Sessions {
    constructor(httpClient) {
        this.httpClient = httpClient;
    }
    /**
     * Get the current session
     */
    async getCurrentSession() {
        const response = await this.httpClient.request({
            method: 'GET',
            url: '/sessions/current'
        });
        return response.data.session;
    }
    /**
     * List all sessions for the current user
     */
    async listSessions(params) {
        const response = await this.httpClient.request({
            method: 'GET',
            url: '/sessions',
            params
        });
        return response.data;
    }
    /**
     * Get a specific session by ID
     */
    async getSession(sessionId) {
        const response = await this.httpClient.request({
            method: 'GET',
            url: `/sessions/${sessionId}`
        });
        return response.data.session;
    }
    /**
     * Revoke a specific session
     */
    async revokeSession(sessionId) {
        await this.httpClient.request({
            method: 'DELETE',
            url: `/sessions/${sessionId}`
        });
    }
    /**
     * Revoke all sessions except the current one
     */
    async revokeAllSessions() {
        const response = await this.httpClient.request({
            method: 'POST',
            url: '/sessions/revoke-all'
        });
        return response.data;
    }
    /**
     * Refresh the current session
     */
    async refreshSession() {
        const response = await this.httpClient.request({
            method: 'POST',
            url: '/sessions/refresh'
        });
        return response.data.session;
    }
    /**
     * Alias for refreshSession for backward compatibility
     */
    async refresh() {
        return this.refreshSession();
    }
    /**
     * Verify if a session is valid
     */
    async verifySession(sessionId) {
        try {
            const session = await this.getSession(sessionId);
            return { valid: !session.revoked, session };
        }
        catch {
            return { valid: false };
        }
    }
}
exports.Sessions = Sessions;
//# sourceMappingURL=sessions.js.map