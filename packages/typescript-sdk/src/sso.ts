/**
 * SSO/SAML module for the Janua TypeScript SDK
 *
 * Provides enterprise Single Sign-On capabilities with SAML 2.0 and OIDC support.
 */

import type { HttpClient } from './http-client';
import type { UUID, ISODateString } from './types';
import { ValidationError } from './errors';
import { ValidationUtils } from './utils';

// SSO Types

export enum SSOProvider {
  SAML = 'saml',
  OIDC = 'oidc',
  GOOGLE_WORKSPACE = 'google_workspace',
  AZURE_AD = 'azure_ad',
  OKTA = 'okta'
}

export enum SSOStatus {
  ACTIVE = 'active',
  PENDING = 'pending',
  DISABLED = 'disabled',
  ERROR = 'error'
}

export interface SSOConfigurationCreate {
  provider: SSOProvider;
  // SAML fields
  saml_metadata_url?: string;
  saml_metadata_xml?: string;
  saml_sso_url?: string;
  saml_slo_url?: string;
  saml_certificate?: string;
  saml_entity_id?: string;
  // OIDC fields
  oidc_issuer?: string;
  oidc_client_id?: string;
  oidc_client_secret?: string;
  oidc_discovery_url?: string;
  // Common settings
  jit_provisioning?: boolean;
  default_role?: string;
  attribute_mapping?: Record<string, string>;
  allowed_domains?: string[];
}

export interface SSOConfigurationUpdate {
  enabled?: boolean;
  // SAML fields
  saml_metadata_url?: string;
  saml_metadata_xml?: string;
  saml_sso_url?: string;
  saml_slo_url?: string;
  saml_certificate?: string;
  // OIDC fields
  oidc_issuer?: string;
  oidc_client_id?: string;
  oidc_client_secret?: string;
  oidc_discovery_url?: string;
  // Settings
  jit_provisioning?: boolean;
  default_role?: string;
  attribute_mapping?: Record<string, string>;
  allowed_domains?: string[];
}

export interface SSOConfiguration {
  id: UUID;
  organization_id: UUID;
  provider: SSOProvider;
  status: SSOStatus;
  enabled: boolean;
  // SAML info (sanitized)
  saml_entity_id?: string;
  saml_acs_url?: string;
  saml_sso_url?: string;
  // OIDC info (sanitized)
  oidc_issuer?: string;
  oidc_client_id?: string;
  oidc_authorization_url?: string;
  // Settings
  jit_provisioning: boolean;
  default_role: string;
  allowed_domains: string[];
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface SSOInitiateRequest {
  organization_slug: string;
  return_url?: string;
}

export interface SSOInitiateResponse {
  redirect_url: string;
  state?: string;
}

export interface SSOTestRequest {
  configuration_id: UUID;
}

export interface SSOTestResponse {
  success: boolean;
  provider: SSOProvider;
  metadata_valid?: boolean;
  connection_status?: 'success' | 'failed' | 'timeout';
  error_message?: string;
  details?: Record<string, any>;
}

/**
 * SSO/SAML management operations
 */
export class SSO {
  constructor(private http: HttpClient) {}

  /**
   * Create SSO configuration for an organization
   *
   * @param organizationId - Organization ID
   * @param config - SSO configuration details
   * @returns Created SSO configuration
   */
  async createConfiguration(
    organizationId: UUID,
    config: SSOConfigurationCreate
  ): Promise<SSOConfiguration> {
    // Validate organization ID
    if (!ValidationUtils.isValidUuid(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    // Validate provider
    if (!Object.values(SSOProvider).includes(config.provider)) {
      throw new ValidationError('Invalid SSO provider');
    }

    // Validate SAML configuration if provider is SAML
    if (config.provider === SSOProvider.SAML) {
      if (!config.saml_metadata_url && !config.saml_metadata_xml && !config.saml_sso_url) {
        throw new ValidationError(
          'SAML configuration requires either metadata URL, metadata XML, or SSO URL'
        );
      }

      if (config.saml_metadata_url && !ValidationUtils.isValidUrl(config.saml_metadata_url)) {
        throw new ValidationError('Invalid SAML metadata URL format');
      }

      if (config.saml_sso_url && !ValidationUtils.isValidUrl(config.saml_sso_url)) {
        throw new ValidationError('Invalid SAML SSO URL format');
      }

      if (config.saml_slo_url && !ValidationUtils.isValidUrl(config.saml_slo_url)) {
        throw new ValidationError('Invalid SAML SLO URL format');
      }
    }

    // Validate OIDC configuration if provider is OIDC
    if (config.provider === SSOProvider.OIDC) {
      if (!config.oidc_issuer || !config.oidc_client_id || !config.oidc_client_secret) {
        throw new ValidationError(
          'OIDC configuration requires issuer, client ID, and client secret'
        );
      }

      if (!ValidationUtils.isValidUrl(config.oidc_issuer)) {
        throw new ValidationError('Invalid OIDC issuer URL format');
      }

      if (config.oidc_discovery_url && !ValidationUtils.isValidUrl(config.oidc_discovery_url)) {
        throw new ValidationError('Invalid OIDC discovery URL format');
      }
    }

    // Validate allowed domains
    if (config.allowed_domains && config.allowed_domains.length > 0) {
      for (const domain of config.allowed_domains) {
        if (!/^[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,}$/i.test(domain)) {
          throw new ValidationError(`Invalid domain format: ${domain}`);
        }
      }
    }

    const response = await this.http.post<SSOConfiguration>(
      `/api/v1/sso/configurations?organization_id=${organizationId}`,
      config
    );
    return response.data;
  }

  /**
   * Get SSO configuration for an organization
   *
   * @param organizationId - Organization ID
   * @returns SSO configuration if exists
   */
  async getConfiguration(organizationId: UUID): Promise<SSOConfiguration> {
    if (!ValidationUtils.isValidUuid(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    const response = await this.http.get<SSOConfiguration>(
      `/api/v1/sso/configurations/${organizationId}`
    );
    return response.data;
  }

  /**
   * Update SSO configuration for an organization
   *
   * @param organizationId - Organization ID
   * @param update - Fields to update
   * @returns Updated SSO configuration
   */
  async updateConfiguration(
    organizationId: UUID,
    update: SSOConfigurationUpdate
  ): Promise<SSOConfiguration> {
    if (!ValidationUtils.isValidUuid(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    // Validate URLs if provided
    if (update.saml_metadata_url && !ValidationUtils.isValidUrl(update.saml_metadata_url)) {
      throw new ValidationError('Invalid SAML metadata URL format');
    }

    if (update.saml_sso_url && !ValidationUtils.isValidUrl(update.saml_sso_url)) {
      throw new ValidationError('Invalid SAML SSO URL format');
    }

    if (update.saml_slo_url && !ValidationUtils.isValidUrl(update.saml_slo_url)) {
      throw new ValidationError('Invalid SAML SLO URL format');
    }

    if (update.oidc_issuer && !ValidationUtils.isValidUrl(update.oidc_issuer)) {
      throw new ValidationError('Invalid OIDC issuer URL format');
    }

    if (update.oidc_discovery_url && !ValidationUtils.isValidUrl(update.oidc_discovery_url)) {
      throw new ValidationError('Invalid OIDC discovery URL format');
    }

    // Validate allowed domains
    if (update.allowed_domains && update.allowed_domains.length > 0) {
      for (const domain of update.allowed_domains) {
        if (!/^[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,}$/i.test(domain)) {
          throw new ValidationError(`Invalid domain format: ${domain}`);
        }
      }
    }

    const response = await this.http.put<SSOConfiguration>(
      `/api/v1/sso/configurations/${organizationId}`,
      update
    );
    return response.data;
  }

  /**
   * Delete SSO configuration for an organization
   *
   * @param organizationId - Organization ID
   * @returns Success message
   */
  async deleteConfiguration(organizationId: UUID): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUuid(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    const response = await this.http.delete<{ message: string }>(
      `/api/v1/sso/configurations/${organizationId}`
    );
    return response.data;
  }

  /**
   * Initiate SSO login flow
   *
   * @param request - Organization slug and optional return URL
   * @returns Redirect URL to identity provider
   */
  async initiateSSO(request: SSOInitiateRequest): Promise<SSOInitiateResponse> {
    if (!request.organization_slug || request.organization_slug.trim().length === 0) {
      throw new ValidationError('Organization slug is required');
    }

    if (!ValidationUtils.isValidSlug(request.organization_slug)) {
      throw new ValidationError('Invalid organization slug format');
    }

    if (request.return_url && !ValidationUtils.isValidUrl(request.return_url)) {
      throw new ValidationError('Invalid return URL format');
    }

    const response = await this.http.post<SSOInitiateResponse>(
      '/api/v1/sso/initiate',
      request
    );
    return response.data;
  }

  /**
   * Test SSO configuration
   *
   * Validates the SSO configuration without initiating a full login flow.
   * Useful for troubleshooting and verification.
   *
   * @param configurationId - SSO configuration ID
   * @returns Test results with connection status
   */
  async testConfiguration(configurationId: UUID): Promise<SSOTestResponse> {
    if (!ValidationUtils.isValidUuid(configurationId)) {
      throw new ValidationError('Invalid configuration ID format');
    }

    const response = await this.http.post<SSOTestResponse>(
      '/api/v1/sso/test',
      { configuration_id: configurationId }
    );
    return response.data;
  }

  /**
   * Generate Service Provider metadata XML for SAML configuration
   *
   * Returns the SP metadata XML that should be uploaded to the identity provider.
   *
   * @param organizationId - Organization ID
   * @returns SP metadata XML string
   */
  async generateSPMetadata(organizationId: UUID): Promise<string> {
    if (!ValidationUtils.isValidUuid(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    const response = await this.http.get<string>(
      `/api/v1/sso/metadata/${organizationId}`
    );
    return response.data;
  }

  /**
   * Enable SSO configuration
   *
   * @param organizationId - Organization ID
   * @returns Updated SSO configuration
   */
  async enableConfiguration(organizationId: UUID): Promise<SSOConfiguration> {
    return this.updateConfiguration(organizationId, { enabled: true });
  }

  /**
   * Disable SSO configuration
   *
   * @param organizationId - Organization ID
   * @returns Updated SSO configuration
   */
  async disableConfiguration(organizationId: UUID): Promise<SSOConfiguration> {
    return this.updateConfiguration(organizationId, { enabled: false });
  }
}
