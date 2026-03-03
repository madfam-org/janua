// Theme and Design System
export * from './theme'
export * from './themes/dual-skin'

// Theme Providers
export { JanuaThemeProvider, useJanuaTheme, type JanuaThemeProviderProps } from './providers'
export { JanuaAuthProvider, useJanuaAuthConfig, type JanuaAuthProviderProps } from './providers'

// Theme Presets
export { defaultPreset, madfamPreset, getPreset, type PresetName } from './tokens/presets'

// Auth Config System
export type { JanuaAuthConfig } from './config/types'
export { defaultAuthConfig, mergeConfig } from './config/defaults'
export { madfamAuthConfig } from './config/madfam-preset'

// Components
export * from './components/button'
export * from './components/card'
export * from './components/input'
export * from './components/label'
export * from './components/badge'
export * from './components/status-badge'
export * from './components/role-badge'
export * from './components/action-menu'
export * from './components/dialog'
export * from './components/toast'
export * from './components/tabs'
export * from './components/error-boundary'
export * from './components/avatar'
export * from './components/separator'
export * from './components/table'
export * from './components/checkbox'
export * from './components/dropdown-menu'
export * from './components/alert-dialog'

// Authentication Components
// Note: Selective export to avoid 'Invitation' type naming collision
// from invitation-list.tsx and invite-user-form.tsx
export {
  // Core Auth Components
  SignIn,
  SignUp,
  UserButton,
  MFASetup,
  MFAChallenge,
  BackupCodes,
  OrganizationSwitcher,
  OrganizationProfile,
  UserProfile,
  PasswordReset,
  EmailVerification,
  PhoneVerification,
  SessionManagement,
  DeviceManagement,
  AuditLog,
  // Shared Sub-Components
  SocialButton,
  GoogleButton,
  GitHubButton,
  MicrosoftButton,
  AppleButton,
  JanuaSSOButton,
  AuthCard,
  AuthDivider,
  PasswordInput,
  calculatePasswordStrength,
  // SSO & Passkey Components
  JanuaSSOLoginButton,
  SSOEmailDetector,
  PasskeyButton,
  MagicLinkForm,
  // Social Icons
  GoogleIcon,
  GitHubIcon,
  MicrosoftIcon,
  AppleIcon,
  JanuaIcon,
  // Enterprise Components
  InvitationList,
  InviteUserForm,
  InvitationAccept,
  BulkInviteUpload,
  SSOProviderList,
  SSOProviderForm,
  SAMLConfigForm,
  SSOTestConnection,
  // Types - with Invitation from invitation-list only
  type Invitation,
  type InvitationCreate,
  type InvitationListParams,
  type InvitationListResponse,
  type InvitationListProps,
  type InviteUserFormProps,
  type BulkInvitationResponse,
  type InvitationValidateResponse,
  type InvitationAcceptRequest,
  type InvitationAcceptResponse,
  type InvitationAcceptProps,
  type BulkInviteUploadProps,
  type SSOProviderListProps,
  type SSOProviderFormProps,
  type SAMLConfigFormProps,
  type SSOTestConnectionProps,
  type SignInProps,
  type SignUpProps,
  type UserButtonProps,
  type MFASetupProps,
  type MFAChallengeProps,
  type BackupCodesProps,
  type OrganizationSwitcherProps,
  type OrganizationProfileProps,
  type UserProfileProps,
  type PasswordResetProps,
  type EmailVerificationProps,
  type PhoneVerificationProps,
  type SessionManagementProps,
  type DeviceManagementProps,
  type AuditLogProps,
  type SocialButtonProps,
  type SocialProvider,
  type AuthCardLayout,
  type AuthCardProps,
  type AuthDividerProps,
  type PasswordInputProps,
  type JanuaSSOButtonProps,
  type SSOEmailDetectorProps,
  type PasskeyButtonProps,
  type MagicLinkFormProps,
} from './components/auth'

// State Management
export * from './stores'

// Theme Toggle
export * from './components/theme-toggle'

// Utilities
export * from './lib/utils'

// Compliance components
export * from './components/compliance'

// SCIM components
export * from './components/scim'

// RBAC components
export * from './components/rbac'
