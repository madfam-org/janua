/**
 * Webhook management module for the Plinto TypeScript SDK
 */

import type { HttpClient } from './http-client';
import type {
  WebhookEndpoint,
  WebhookEndpointCreateRequest,
  WebhookEndpointUpdateRequest,
  WebhookEvent,
  WebhookDelivery,
  WebhookEventType
} from './types';
import { ValidationError, WebhookError } from './errors';
import { ValidationUtils, WebhookUtils } from './utils';

/**
 * Webhook management operations
 */
export class Webhooks {
  constructor(private http: HttpClient) {}

  /**
   * Create a new webhook endpoint
   */
  async createEndpoint(request: WebhookEndpointCreateRequest): Promise<WebhookEndpoint> {
    // Validate input
    if (!ValidationUtils.isValidUrl(request.url)) {
      throw new ValidationError('Invalid webhook URL format');
    }

    if (!request.events || request.events.length === 0) {
      throw new ValidationError('At least one event type must be specified');
    }

    // Validate event types
    const validEvents = Object.values(WebhookEventType);
    const invalidEvents = request.events.filter(event => !validEvents.includes(event));
    if (invalidEvents.length > 0) {
      throw new ValidationError(`Invalid event types: ${invalidEvents.join(', ')}`);
    }

    if (request.description && request.description.length > 500) {
      throw new ValidationError('Description must be 500 characters or less');
    }

    // Validate custom headers
    if (request.headers) {
      const invalidHeaders = Object.keys(request.headers).filter(key => 
        key.toLowerCase().startsWith('authorization') || 
        key.toLowerCase().startsWith('x-webhook')
      );
      if (invalidHeaders.length > 0) {
        throw new ValidationError(`Reserved header names cannot be used: ${invalidHeaders.join(', ')}`);
      }
    }

    const response = await this.http.post<WebhookEndpoint>('/api/v1/webhooks/', request);
    return response.data;
  }

  /**
   * List webhook endpoints for current user
   */
  async listEndpoints(isActive?: boolean): Promise<{
    endpoints: WebhookEndpoint[];
    total: number;
  }> {
    const params: Record<string, any> = {};
    if (isActive !== undefined) {
      params.is_active = isActive;
    }

    const response = await this.http.get<{
      endpoints: WebhookEndpoint[];
      total: number;
    }>('/api/v1/webhooks/', { params });
    return response.data;
  }

  /**
   * Get webhook endpoint details
   */
  async getEndpoint(endpointId: string): Promise<WebhookEndpoint> {
    if (!ValidationUtils.isValidUUID(endpointId)) {
      throw new ValidationError('Invalid endpoint ID format');
    }

    const response = await this.http.get<WebhookEndpoint>(`/api/v1/webhooks/${endpointId}`);
    return response.data;
  }

  /**
   * Update webhook endpoint
   */
  async updateEndpoint(
    endpointId: string,
    request: WebhookEndpointUpdateRequest
  ): Promise<WebhookEndpoint> {
    if (!ValidationUtils.isValidUUID(endpointId)) {
      throw new ValidationError('Invalid endpoint ID format');
    }

    // Validate input
    if (request.url && !ValidationUtils.isValidUrl(request.url)) {
      throw new ValidationError('Invalid webhook URL format');
    }

    if (request.events) {
      if (request.events.length === 0) {
        throw new ValidationError('At least one event type must be specified');
      }

      const validEvents = Object.values(WebhookEventType);
      const invalidEvents = request.events.filter(event => !validEvents.includes(event));
      if (invalidEvents.length > 0) {
        throw new ValidationError(`Invalid event types: ${invalidEvents.join(', ')}`);
      }
    }

    if (request.description && request.description.length > 500) {
      throw new ValidationError('Description must be 500 characters or less');
    }

    if (request.headers) {
      const invalidHeaders = Object.keys(request.headers).filter(key => 
        key.toLowerCase().startsWith('authorization') || 
        key.toLowerCase().startsWith('x-webhook')
      );
      if (invalidHeaders.length > 0) {
        throw new ValidationError(`Reserved header names cannot be used: ${invalidHeaders.join(', ')}`);
      }
    }

    const response = await this.http.patch<WebhookEndpoint>(`/api/v1/webhooks/${endpointId}`, request);
    return response.data;
  }

  /**
   * Delete webhook endpoint
   */
  async deleteEndpoint(endpointId: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(endpointId)) {
      throw new ValidationError('Invalid endpoint ID format');
    }

    const response = await this.http.delete<{ message: string }>(`/api/v1/webhooks/${endpointId}`);
    return response.data;
  }

  /**
   * Test webhook endpoint
   */
  async testEndpoint(endpointId: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(endpointId)) {
      throw new ValidationError('Invalid endpoint ID format');
    }

    const response = await this.http.post<{ message: string }>(`/api/v1/webhooks/${endpointId}/test`);
    return response.data;
  }

  /**
   * Get webhook endpoint statistics
   */
  async getEndpointStats(endpointId: string, days = 7): Promise<{
    total_deliveries: number;
    successful: number;
    failed: number;
    success_rate: number;
    average_delivery_time: number;
    period_days: number;
  }> {
    if (!ValidationUtils.isValidUUID(endpointId)) {
      throw new ValidationError('Invalid endpoint ID format');
    }

    if (days < 1 || days > 90) {
      throw new ValidationError('Days must be between 1 and 90');
    }

    const response = await this.http.get(`/api/v1/webhooks/${endpointId}/stats`, {
      params: { days }
    });
    return response.data;
  }

  /**
   * List webhook events for an endpoint
   */
  async listEvents(
    endpointId: string,
    options?: {
      limit?: number;
      offset?: number;
    }
  ): Promise<{
    events: WebhookEvent[];
    total: number;
  }> {
    if (!ValidationUtils.isValidUUID(endpointId)) {
      throw new ValidationError('Invalid endpoint ID format');
    }

    const params: Record<string, any> = {};
    if (options?.limit !== undefined) {
      if (options.limit < 1 || options.limit > 1000) {
        throw new ValidationError('Limit must be between 1 and 1000');
      }
      params.limit = options.limit;
    }

    if (options?.offset !== undefined) {
      if (options.offset < 0) {
        throw new ValidationError('Offset must be non-negative');
      }
      params.offset = options.offset;
    }

    const response = await this.http.get<{
      events: WebhookEvent[];
      total: number;
    }>(`/api/v1/webhooks/${endpointId}/events`, { params });
    return response.data;
  }

  /**
   * List webhook delivery attempts for an endpoint
   */
  async listDeliveries(
    endpointId: string,
    options?: {
      limit?: number;
      offset?: number;
    }
  ): Promise<WebhookDelivery[]> {
    if (!ValidationUtils.isValidUUID(endpointId)) {
      throw new ValidationError('Invalid endpoint ID format');
    }

    const params: Record<string, any> = {};
    if (options?.limit !== undefined) {
      if (options.limit < 1 || options.limit > 1000) {
        throw new ValidationError('Limit must be between 1 and 1000');
      }
      params.limit = options.limit;
    }

    if (options?.offset !== undefined) {
      if (options.offset < 0) {
        throw new ValidationError('Offset must be non-negative');
      }
      params.offset = options.offset;
    }

    const response = await this.http.get<WebhookDelivery[]>(`/api/v1/webhooks/${endpointId}/deliveries`, {
      params
    });
    return response.data;
  }

  /**
   * Regenerate webhook endpoint secret
   */
  async regenerateSecret(endpointId: string): Promise<WebhookEndpoint> {
    if (!ValidationUtils.isValidUUID(endpointId)) {
      throw new ValidationError('Invalid endpoint ID format');
    }

    const response = await this.http.post<WebhookEndpoint>(`/api/v1/webhooks/${endpointId}/regenerate-secret`);
    return response.data;
  }

  /**
   * Get available webhook event types
   */
  async getEventTypes(): Promise<string[]> {
    const response = await this.http.get<string[]>('/api/v1/webhooks/events/types');
    return response.data;
  }

  /**
   * Verify webhook signature (for testing)
   */
  async verifySignature(
    secret: string,
    payload: string,
    signature: string
  ): Promise<{ valid: boolean }> {
    if (!secret || !payload || !signature) {
      throw new ValidationError('Secret, payload, and signature are all required');
    }

    const response = await this.http.post<{ valid: boolean }>('/api/v1/webhooks/verify-signature', {
      secret,
      payload,
      signature
    });
    return response.data;
  }

  // Client-side utilities

  /**
   * Verify webhook signature (client-side)
   */
  async verifyWebhookSignature(
    payload: string,
    signature: string,
    secret: string
  ): Promise<boolean> {
    try {
      return await WebhookUtils.verifySignature(payload, signature, secret);
    } catch (error) {
      throw new WebhookError('Failed to verify webhook signature', { originalError: error });
    }
  }

  /**
   * Parse webhook payload
   */
  parseWebhookPayload<T = any>(payload: string): {
    event: WebhookEventType;
    data: T;
    timestamp: string;
    id: string;
  } {
    try {
      const parsed = JSON.parse(payload);
      
      if (!parsed.event || !parsed.data || !parsed.timestamp || !parsed.id) {
        throw new WebhookError('Invalid webhook payload format');
      }

      if (!Object.values(WebhookEventType).includes(parsed.event)) {
        throw new WebhookError(`Unknown webhook event type: ${parsed.event}`);
      }

      return parsed;
    } catch (error) {
      if (error instanceof WebhookError) {
        throw error;
      }
      throw new WebhookError('Failed to parse webhook payload', { originalError: error });
    }
  }

  /**
   * Validate webhook endpoint URL
   */
  validateEndpointUrl(url: string): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!url) {
      errors.push('URL is required');
      return { valid: false, errors };
    }

    if (!ValidationUtils.isValidUrl(url)) {
      errors.push('Invalid URL format');
      return { valid: false, errors };
    }

    try {
      const urlObj = new URL(url);
      
      // Must use HTTPS in production
      if (urlObj.protocol !== 'https:' && urlObj.protocol !== 'http:') {
        errors.push('URL must use HTTP or HTTPS protocol');
      }

      // Recommend HTTPS
      if (urlObj.protocol === 'http:') {
        errors.push('HTTPS is recommended for webhook endpoints');
      }

      // Check for localhost/private IPs in production
      const hostname = urlObj.hostname;
      if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.endsWith('.local')) {
        errors.push('Localhost URLs are not recommended for production webhooks');
      }

      // Check for standard webhook path
      if (!urlObj.pathname.includes('webhook')) {
        errors.push('Consider using a path that includes "webhook" for clarity');
      }

    } catch (error) {
      errors.push('Invalid URL format');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Get webhook event categories
   */
  getEventCategories(): Record<string, WebhookEventType[]> {
    return {
      user: [
        WebhookEventType.USER_CREATED,
        WebhookEventType.USER_UPDATED,
        WebhookEventType.USER_DELETED,
        WebhookEventType.USER_SIGNED_IN,
        WebhookEventType.USER_SIGNED_OUT
      ],
      session: [
        WebhookEventType.SESSION_CREATED,
        WebhookEventType.SESSION_EXPIRED
      ],
      organization: [
        WebhookEventType.ORGANIZATION_CREATED,
        WebhookEventType.ORGANIZATION_UPDATED,
        WebhookEventType.ORGANIZATION_DELETED,
        WebhookEventType.ORGANIZATION_MEMBER_ADDED,
        WebhookEventType.ORGANIZATION_MEMBER_REMOVED
      ]
    };
  }

  /**
   * Get friendly event type names
   */
  getEventTypeNames(): Record<WebhookEventType, string> {
    return {
      [WebhookEventType.USER_CREATED]: 'User Created',
      [WebhookEventType.USER_UPDATED]: 'User Updated',
      [WebhookEventType.USER_DELETED]: 'User Deleted',
      [WebhookEventType.USER_SIGNED_IN]: 'User Signed In',
      [WebhookEventType.USER_SIGNED_OUT]: 'User Signed Out',
      [WebhookEventType.SESSION_CREATED]: 'Session Created',
      [WebhookEventType.SESSION_EXPIRED]: 'Session Expired',
      [WebhookEventType.ORGANIZATION_CREATED]: 'Organization Created',
      [WebhookEventType.ORGANIZATION_UPDATED]: 'Organization Updated',
      [WebhookEventType.ORGANIZATION_DELETED]: 'Organization Deleted',
      [WebhookEventType.ORGANIZATION_MEMBER_ADDED]: 'Organization Member Added',
      [WebhookEventType.ORGANIZATION_MEMBER_REMOVED]: 'Organization Member Removed'
    };
  }

  /**
   * Calculate delivery success rate
   */
  calculateSuccessRate(stats: {
    total_deliveries: number;
    successful: number;
    failed: number;
  }): {
    rate: number;
    status: 'excellent' | 'good' | 'fair' | 'poor';
  } {
    if (stats.total_deliveries === 0) {
      return { rate: 0, status: 'poor' };
    }

    const rate = (stats.successful / stats.total_deliveries) * 100;

    let status: 'excellent' | 'good' | 'fair' | 'poor';
    if (rate >= 95) status = 'excellent';
    else if (rate >= 90) status = 'good';
    else if (rate >= 75) status = 'fair';
    else status = 'poor';

    return { rate, status };
  }

  /**
   * Format webhook endpoint for display
   */
  formatEndpoint(endpoint: WebhookEndpoint): {
    displayUrl: string;
    eventCount: number;
    statusText: string;
    isHealthy: boolean;
  } {
    // Truncate URL for display
    let displayUrl = endpoint.url;
    if (displayUrl.length > 50) {
      displayUrl = displayUrl.substring(0, 47) + '...';
    }

    return {
      displayUrl,
      eventCount: endpoint.events.length,
      statusText: endpoint.is_active ? 'Active' : 'Inactive',
      isHealthy: endpoint.is_active
    };
  }
}