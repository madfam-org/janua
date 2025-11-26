/**
 * Auth module exports
 *
 * This module provides focused authentication services extracted from the main Auth class.
 * Each service handles a specific authentication domain for better maintainability.
 */

// Core service
export { CoreAuthService } from './core-auth-service';

// Domain-specific services
export { PasswordService } from './password-service';
export { EmailVerificationService } from './email-verification-service';
export { MagicLinkService } from './magic-link-service';
export { MFAService } from './mfa-service';
export { OAuthService } from './oauth-service';
export { PasskeyService, type PasskeyRegistrationOptions, type PasskeyAuthenticationOptions } from './passkey-service';
