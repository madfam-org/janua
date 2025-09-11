/**
 * Core types and interfaces for the Plinto TypeScript SDK
 */

// Base Types
export type UUID = string;
export type ISODateString = string;

// Environment Types
export type Environment = 'production' | 'staging' | 'development';

// User Status
export enum UserStatus {
  ACTIVE = 'active',
  SUSPENDED = 'suspended',
  DELETED = 'deleted'
}

// Organization Roles
export enum OrganizationRole {
  OWNER = 'owner',
  ADMIN = 'admin',
  MEMBER = 'member',
  VIEWER = 'viewer'
}

// OAuth Providers
export enum OAuthProvider {
  GOOGLE = 'google',
  GITHUB = 'github',
  MICROSOFT = 'microsoft',
  DISCORD = 'discord',
  TWITTER = 'twitter'
}

// Webhook Event Types
export enum WebhookEventType {
  USER_CREATED = 'user.created',
  USER_UPDATED = 'user.updated',
  USER_DELETED = 'user.deleted',
  USER_SIGNED_IN = 'user.signed_in',
  USER_SIGNED_OUT = 'user.signed_out',
  SESSION_CREATED = 'session.created',
  SESSION_EXPIRED = 'session.expired',
  ORGANIZATION_CREATED = 'organization.created',
  ORGANIZATION_UPDATED = 'organization.updated',
  ORGANIZATION_DELETED = 'organization.deleted',
  ORGANIZATION_MEMBER_ADDED = 'organization.member_added',
  ORGANIZATION_MEMBER_REMOVED = 'organization.member_removed'
}

// Core Interfaces

export interface User {
  id: UUID;
  email: string;
  email_verified: boolean;
  username?: string;
  first_name?: string;
  last_name?: string;
  display_name?: string;
  profile_image_url?: string;
  bio?: string;
  phone_number?: string;
  phone_verified: boolean;
  timezone?: string;
  locale?: string;
  status: UserStatus;
  mfa_enabled: boolean;
  is_admin: boolean;
  created_at: ISODateString;
  updated_at: ISODateString;
  last_sign_in_at?: ISODateString;
  user_metadata: Record<string, any>;
}

export interface Session {
  id: UUID;
  user_id: UUID;
  ip_address?: string;
  user_agent?: string;
  device_name?: string;
  device_type?: string;
  browser?: string;
  os?: string;
  is_current: boolean;
  created_at: ISODateString;
  last_activity_at: ISODateString;
  expires_at: ISODateString;
  revoked: boolean;
}

export interface Organization {
  id: UUID;
  name: string;
  slug: string;
  description?: string;
  logo_url?: string;
  owner_id: UUID;
  settings: Record<string, any>;
  org_metadata: Record<string, any>;
  billing_email?: string;
  billing_plan: string;
  created_at: ISODateString;
  updated_at: ISODateString;
  member_count: number;
  is_owner: boolean;
  user_role?: OrganizationRole;
}

export interface OrganizationMember {
  user_id: UUID;
  email: string;
  first_name?: string;
  last_name?: string;
  display_name?: string;
  profile_image_url?: string;
  role: OrganizationRole;
  permissions: string[];
  joined_at: ISODateString;
  invited_by?: UUID;
}

export interface OrganizationInvitation {
  id: UUID;
  organization_id: UUID;
  organization_name: string;
  email: string;
  role: OrganizationRole;
  permissions: string[];
  invited_by: UUID;
  inviter_name?: string;
  status: 'pending' | 'accepted' | 'expired';
  created_at: ISODateString;
  expires_at: ISODateString;
}

export interface Passkey {
  id: UUID;
  name?: string;
  authenticator_attachment?: string;
  created_at: ISODateString;
  last_used_at?: ISODateString;
  sign_count: number;
}

export interface WebhookEndpoint {
  id: UUID;
  url: string;
  secret: string;
  events: WebhookEventType[];
  is_active: boolean;
  description?: string;
  headers?: Record<string, string>;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface WebhookEvent {
  id: UUID;
  type: WebhookEventType;
  data: Record<string, any>;
  created_at: ISODateString;
}

export interface WebhookDelivery {
  id: UUID;
  webhook_endpoint_id: UUID;
  webhook_event_id: UUID;
  status_code?: number;
  response_body?: string;
  error?: string;
  attempt: number;
  delivered_at?: ISODateString;
  created_at: ISODateString;
}

// Request Types

export interface SignUpRequest {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  username?: string;
}

export interface SignInRequest {
  email?: string;
  username?: string;
  password: string;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface MagicLinkRequest {
  email: string;
  redirect_url?: string;
}

export interface UserUpdateRequest {
  first_name?: string;
  last_name?: string;
  display_name?: string;
  bio?: string;
  phone_number?: string;
  timezone?: string;
  locale?: string;
  user_metadata?: Record<string, any>;
}

export interface OrganizationCreateRequest {
  name: string;
  slug: string;
  description?: string;
  billing_email?: string;
}

export interface OrganizationUpdateRequest {
  name?: string;
  description?: string;
  logo_url?: string;
  billing_email?: string;
  settings?: Record<string, any>;
}

export interface OrganizationInviteRequest {
  email: string;
  role: OrganizationRole;
  permissions?: string[];
  message?: string;
}

export interface WebhookEndpointCreateRequest {
  url: string;
  events: WebhookEventType[];
  description?: string;
  headers?: Record<string, string>;
}

export interface WebhookEndpointUpdateRequest {
  url?: string;
  events?: WebhookEventType[];
  is_active?: boolean;
  description?: string;
  headers?: Record<string, string>;
}

export interface MFAEnableRequest {
  password: string;
}

export interface MFAVerifyRequest {
  code: string;
}

export interface MFADisableRequest {
  password: string;
  code?: string;
}

// Response Types

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface AuthResponse {
  user: User;
  tokens: TokenResponse;
}

export interface MFAEnableResponse {
  secret: string;
  qr_code: string;
  backup_codes: string[];
  provisioning_uri: string;
}

export interface MFAStatusResponse {
  enabled: boolean;
  verified: boolean;
  backup_codes_remaining: number;
  last_used_at?: ISODateString;
}

export interface MFABackupCodesResponse {
  backup_codes: string[];
  generated_at: ISODateString;
}

export interface OAuthProvidersResponse {
  providers: Array<{
    provider: string;
    name: string;
    enabled: boolean;
  }>;
}

export interface LinkedAccountsResponse {
  oauth_accounts: Array<{
    provider: string;
    name: string;
    linked: boolean;
    enabled: boolean;
    provider_email?: string;
    linked_at?: ISODateString;
    last_updated?: ISODateString;
  }>;
  auth_methods: {
    password: boolean;
    mfa_enabled: boolean;
    passkeys_count: number;
  };
  total_linked: number;
}

export interface AdminStatsResponse {
  total_users: number;
  active_users: number;
  suspended_users: number;
  deleted_users: number;
  total_organizations: number;
  total_sessions: number;
  active_sessions: number;
  mfa_enabled_users: number;
  oauth_accounts: number;
  passkeys_registered: number;
  users_last_24h: number;
  sessions_last_24h: number;
}

export interface SystemHealthResponse {
  status: string;
  database: string;
  cache: string;
  storage: string;
  email: string;
  uptime: number;
  version: string;
  environment: string;
}

// Pagination
export interface PaginationParams {
  page?: number;
  per_page?: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// Search and Filter Types
export interface UserListParams extends PaginationParams {
  search?: string;
  status?: UserStatus;
}

export interface OrganizationListParams extends PaginationParams {
  search?: string;
  billing_plan?: string;
}

export interface SessionListParams extends PaginationParams {
  active_only?: boolean;
}

// Error Types
export interface ApiError {
  error: string;
  message: string;
  details?: Record<string, any>;
  status_code: number;
}

// SDK Configuration
export interface PlintoConfig {
  baseURL: string;
  apiKey?: string;
  timeout?: number;
  retryAttempts?: number;
  retryDelay?: number;
  environment?: Environment;
  debug?: boolean;
  autoRefreshTokens?: boolean;
  tokenStorage?: 'localStorage' | 'sessionStorage' | 'memory' | 'custom';
  customStorage?: {
    getItem: (key: string) => string | null | Promise<string | null>;
    setItem: (key: string, value: string) => void | Promise<void>;
    removeItem: (key: string) => void | Promise<void>;
  };
}

// HTTP Client Types
export interface RequestConfig {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  url: string;
  data?: any;
  params?: Record<string, any>;
  headers?: Record<string, string>;
  timeout?: number;
  skipAuth?: boolean;
}

export interface HttpResponse<T = any> {
  data: T;
  status: number;
  statusText: string;
  headers: Record<string, string>;
}

// Token Storage
export interface TokenData {
  access_token: string;
  refresh_token: string;
  expires_at: number;
}

// Event Types for SDK
export interface SdkEventMap {
  'token:refreshed': { tokens: TokenResponse };
  'token:expired': {};
  'auth:signedIn': { user: User };
  'auth:signedOut': {};
  'error': { error: any };
}

export type SdkEventType = keyof SdkEventMap;
export type SdkEventHandler<T extends SdkEventType> = (data: SdkEventMap[T]) => void;

// Rate Limiting
export interface RateLimitInfo {
  limit: number;
  remaining: number;
  reset: number;
  retry_after?: number;
}