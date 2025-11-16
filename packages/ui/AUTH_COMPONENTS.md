# Plinto UI - Authentication Components

Production-ready authentication components for React applications. These components are designed to match Clerk's developer experience while integrating seamlessly with the Plinto authentication platform.

## 🎨 Components

### SignIn

A complete sign-in component with email/password and social login support.

```tsx
import { SignIn } from '@plinto/ui'

function App() {
  return (
    <SignIn
      redirectUrl="/dashboard"
      signUpUrl="/sign-up"
      socialProviders={{
        google: true,
        github: true,
        microsoft: false,
        apple: false,
      }}
      afterSignIn={(user) => {
        console.log('User signed in:', user)
      }}
      appearance={{
        theme: 'light',
        variables: {
          colorPrimary: '#3b82f6',
        },
      }}
      logoUrl="/logo.png"
      showRememberMe={true}
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `redirectUrl?`: URL to redirect after sign-in
- `signUpUrl?`: URL to sign-up page
- `afterSignIn?`: Callback after successful sign-in
- `onError?`: Callback on error
- `appearance?`: Theme customization
- `socialProviders?`: Enable/disable social providers
- `logoUrl?`: Custom logo URL
- `showRememberMe?`: Show "Remember me" checkbox (default: `true`)

---

### SignUp

A complete registration component with validation and password strength meter.

```tsx
import { SignUp } from '@plinto/ui'

function App() {
  return (
    <SignUp
      redirectUrl="/onboarding"
      signInUrl="/sign-in"
      socialProviders={{
        google: true,
        github: true,
      }}
      afterSignUp={(user) => {
        console.log('User registered:', user)
      }}
      requireEmailVerification={true}
      showPasswordStrength={true}
      logoUrl="/logo.png"
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `redirectUrl?`: URL to redirect after sign-up
- `signInUrl?`: URL to sign-in page
- `afterSignUp?`: Callback after successful sign-up
- `onError?`: Callback on error
- `appearance?`: Theme customization
- `socialProviders?`: Enable/disable social providers
- `logoUrl?`: Custom logo URL
- `requireEmailVerification?`: Require email verification (default: `true`)
- `showPasswordStrength?`: Show password strength meter (default: `true`)

**Features:**
- ✅ Password strength meter with visual feedback
- ✅ Real-time validation
- ✅ First name + last name fields
- ✅ Terms of service checkbox
- ✅ Social sign-up options

---

### UserButton

A user profile dropdown menu with account management and sign-out.

```tsx
import { UserButton } from '@plinto/ui'

function App() {
  const user = {
    id: '123',
    email: 'john@example.com',
    firstName: 'John',
    lastName: 'Doe',
    avatarUrl: 'https://example.com/avatar.jpg',
  }

  return (
    <UserButton
      user={user}
      onSignOut={() => {
        // Handle sign out
        console.log('User signed out')
      }}
      showManageAccount={true}
      manageAccountUrl="/account"
      showOrganizations={true}
    />
  )
}
```

**Props:**
- `user`: User data object (required)
  - `id`: User ID
  - `email`: User email
  - `firstName?`: First name
  - `lastName?`: Last name
  - `avatarUrl?`: Avatar image URL
- `onSignOut?`: Callback when user signs out
- `showManageAccount?`: Show manage account option (default: `true`)
- `manageAccountUrl?`: Custom manage account URL (default: `/account`)
- `showOrganizations?`: Show organization switcher (default: `false`)
- `className?`: Optional custom class name

**Features:**
- ✅ User avatar with fallback to initials
- ✅ Account management link
- ✅ Settings link
- ✅ Organization switcher (optional)
- ✅ Sign out action

---

## 🎨 Theming

All components support theme customization through the `appearance` prop:

```tsx
<SignIn
  appearance={{
    theme: 'dark',
    variables: {
      colorPrimary: '#3b82f6',
      colorBackground: '#ffffff',
      colorText: '#000000',
    },
  }}
/>
```

## 🌐 Social Providers

Configure which social login providers to display:

```tsx
<SignIn
  socialProviders={{
    google: true,    // Google OAuth
    github: true,    // GitHub OAuth
    microsoft: true, // Microsoft OAuth
    apple: true,     // Apple Sign In
  }}
/>
```

**Supported Providers:**
- ✅ Google
- ✅ GitHub
- ✅ Microsoft
- ✅ Apple

## 🔐 Integration with Plinto SDK

These components are designed to work seamlessly with the Plinto authentication SDK:

```tsx
import { PlintoProvider } from '@plinto/react'
import { SignIn } from '@plinto/ui'

function App() {
  return (
    <PlintoProvider
      apiUrl={process.env.NEXT_PUBLIC_API_URL}
      apiKey={process.env.NEXT_PUBLIC_PLINTO_KEY}
    >
      <SignIn
        afterSignIn={async (user) => {
          // User is automatically authenticated via Plinto context
          console.log('Authenticated user:', user)
        }}
      />
    </PlintoProvider>
  )
}
```

## 📱 Responsive Design

All components are fully responsive and mobile-optimized:

- Desktop: Full-width with max-width constraints
- Tablet: Optimized layout with touch-friendly buttons
- Mobile: Stack elements vertically, larger touch targets

## ♿ Accessibility

Components follow WCAG 2.1 AA accessibility standards:

- ✅ Keyboard navigation
- ✅ Screen reader support
- ✅ ARIA labels and roles
- ✅ Focus management
- ✅ Color contrast compliance

## 🧪 Testing

Components are fully tested with:

- Unit tests (Vitest + React Testing Library)
- Integration tests
- Accessibility tests
- Visual regression tests (Storybook)

## 📖 Examples

### Next.js App Router

```tsx
// app/sign-in/page.tsx
import { SignIn } from '@plinto/ui'

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <SignIn
        redirectUrl="/dashboard"
        signUpUrl="/sign-up"
      />
    </div>
  )
}
```

### Next.js Pages Router

```tsx
// pages/sign-in.tsx
import { SignIn } from '@plinto/ui'

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <SignIn
        redirectUrl="/dashboard"
        signUpUrl="/sign-up"
      />
    </div>
  )
}
```

### React (Vite/CRA)

```tsx
// src/pages/SignIn.tsx
import { SignIn } from '@plinto/ui'
import '@plinto/ui/globals.css' // Import global styles

export function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <SignIn
        redirectUrl="/dashboard"
        signUpUrl="/sign-up"
      />
    </div>
  )
}
```

## 🎨 Additional Components

### MFASetup

Multi-factor authentication enrollment component with QR code generation.

```tsx
import { MFASetup } from '@plinto/ui'

function App() {
  return (
    <MFASetup
      onFetchSetupData={async () => {
        // Fetch MFA setup data from your backend
        return {
          secret: 'JBSWY3DPEHPK3PXP',
          qrCode: 'data:image/png;base64,...',
          backupCodes: ['abc123', 'def456', ...]
        }
      }}
      onComplete={async (verificationCode) => {
        // Verify the code and enable MFA
        await enableMFA(verificationCode)
      }}
      showBackupCodes={true}
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `mfaData?`: Pre-loaded MFA setup data
- `onFetchSetupData?`: Callback to fetch setup data
- `onComplete?`: Callback after successful MFA setup
- `onError?`: Callback on error
- `onCancel?`: Callback to cancel setup
- `showBackupCodes?`: Show backup codes step (default: `true`)

**Features:**
- ✅ Three-step wizard (scan → verify → backup codes)
- ✅ QR code display for authenticator apps
- ✅ Manual secret entry with copy button
- ✅ 6-digit code verification
- ✅ Backup codes with download option

---

### MFAChallenge

Multi-factor authentication verification component for sign-in flow.

```tsx
import { MFAChallenge } from '@plinto/ui'

function App() {
  return (
    <MFAChallenge
      userEmail="user@example.com"
      method="totp"
      onVerify={async (code) => {
        // Verify the MFA code
        await verifyMFACode(code)
      }}
      onUseBackupCode={() => {
        // Switch to backup code entry
        setMFAMethod('backup')
      }}
      showBackupCodeOption={true}
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `userEmail?`: User identifier for display
- `onVerify?`: Callback when code is verified
- `onUseBackupCode?`: Callback to use backup code instead
- `onRequestNewCode?`: Callback to request new code (SMS)
- `onError?`: Callback on error
- `method?`: MFA method type (`'totp'` | `'sms'`)
- `showBackupCodeOption?`: Show use backup code option (default: `true`)
- `allowResend?`: Allow resending code for SMS (default: `false`)

**Features:**
- ✅ 6-digit code input with auto-submit
- ✅ Support for TOTP and SMS methods
- ✅ Resend code functionality with cooldown
- ✅ Use backup code option
- ✅ Error handling with attempt tracking
- ✅ Help text with troubleshooting tips

---

### BackupCodes

Backup code management component for viewing and regenerating recovery codes.

```tsx
import { BackupCodes } from '@plinto/ui'

function App() {
  return (
    <BackupCodes
      onFetchCodes={async () => {
        // Fetch backup codes from your backend
        return [
          { code: 'abc123', used: false },
          { code: 'def456', used: true },
          ...
        ]
      }}
      onRegenerateCodes={async () => {
        // Regenerate new backup codes
        return await generateNewBackupCodes()
      }}
      allowRegeneration={true}
      showDownload={true}
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `backupCodes?`: List of backup codes with usage status
- `onFetchCodes?`: Callback to fetch backup codes
- `onRegenerateCodes?`: Callback to regenerate backup codes
- `onError?`: Callback on error
- `allowRegeneration?`: Allow regeneration of codes (default: `true`)
- `showDownload?`: Show download option (default: `true`)

**Features:**
- ✅ Display of used/unused backup codes
- ✅ Copy individual codes to clipboard
- ✅ Download codes as text file
- ✅ Regenerate codes with confirmation
- ✅ Visual indication of used codes
- ✅ Low code count warnings

---

### OrganizationSwitcher

Multi-tenant organization switching component with dropdown menu.

```tsx
import { OrganizationSwitcher } from '@plinto/ui'

function App() {
  return (
    <OrganizationSwitcher
      currentOrganization={{
        id: '123',
        name: 'Acme Inc',
        slug: 'acme',
        role: 'admin',
        logoUrl: '/acme-logo.png',
        memberCount: 15
      }}
      onFetchOrganizations={async () => {
        // Fetch user's organizations
        return await getUserOrganizations()
      }}
      onSwitchOrganization={(org) => {
        // Switch to selected organization
        setCurrentOrg(org)
      }}
      onCreateOrganization={() => {
        // Navigate to create org flow
        navigate('/org/create')
      }}
      showPersonalWorkspace={true}
      showCreateOrganization={true}
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `currentOrganization?`: Currently active organization
- `organizations?`: List of organizations user belongs to
- `onFetchOrganizations?`: Callback to fetch organizations
- `onSwitchOrganization?`: Callback when organization is switched
- `onCreateOrganization?`: Callback to create new organization
- `onError?`: Callback on error
- `showCreateOrganization?`: Show create organization option (default: `true`)
- `showPersonalWorkspace?`: Show personal workspace option (default: `true`)
- `personalWorkspace?`: Personal workspace data

**Features:**
- ✅ Dropdown menu with organization list
- ✅ Organization logos with fallback to initials
- ✅ Role badges (owner, admin, member)
- ✅ Member count display
- ✅ Personal workspace option
- ✅ Create new organization action
- ✅ Keyboard navigation

---

### OrganizationProfile

Complete organization settings management component with tabs.

```tsx
import { OrganizationProfile } from '@plinto/ui'

function App() {
  return (
    <OrganizationProfile
      organization={{
        id: '123',
        name: 'Acme Inc',
        slug: 'acme',
        description: 'Building amazing products',
        logoUrl: '/acme-logo.png',
        memberCount: 15
      }}
      userRole="admin"
      onUpdateOrganization={async (data) => {
        // Update organization settings
        await updateOrganization(data)
      }}
      onUploadLogo={async (file) => {
        // Upload new organization logo
        return await uploadOrgLogo(file)
      }}
      onFetchMembers={async () => {
        // Fetch organization members
        return await getOrgMembers()
      }}
      onInviteMember={async (email, role) => {
        // Invite new member
        await inviteMember(email, role)
      }}
      onUpdateMemberRole={async (memberId, role) => {
        // Update member role
        await updateMemberRole(memberId, role)
      }}
      onRemoveMember={async (memberId) => {
        // Remove member from organization
        await removeMember(memberId)
      }}
      onDeleteOrganization={async () => {
        // Delete the organization
        await deleteOrganization()
      }}
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `organization`: Organization data (required)
- `userRole`: Current user's role (`'owner'` | `'admin'` | `'member'`)
- `members?`: Organization members
- `onUpdateOrganization?`: Callback to update organization
- `onUploadLogo?`: Callback to upload organization logo
- `onFetchMembers?`: Callback to fetch members
- `onInviteMember?`: Callback to invite member
- `onUpdateMemberRole?`: Callback to update member role
- `onRemoveMember?`: Callback to remove member
- `onDeleteOrganization?`: Callback to delete organization
- `onError?`: Callback on error

**Features:**
- ✅ Three-tab interface (General, Members, Danger Zone)
- ✅ Organization name, slug, and description editing
- ✅ Logo upload with preview
- ✅ Member list with avatars and roles
- ✅ Invite members with role selection
- ✅ Update member roles (admin/member)
- ✅ Remove members
- ✅ Delete organization with confirmation
- ✅ Permission-based UI (owner/admin/member)

---

## 🎨 Additional Components (Week 3)

### UserProfile

Complete user profile management component with tabs for profile, security, and account settings.

```tsx
import { UserProfile } from '@plinto/ui'

function ProfilePage() {
  return (
    <UserProfile
      user={{
        id: '123',
        email: 'user@example.com',
        firstName: 'John',
        lastName: 'Doe',
        avatarUrl: '/avatar.jpg',
        twoFactorEnabled: true,
        emailVerified: true,
      }}
      onUpdateProfile={async (data) => {
        await updateProfile(data)
      }}
      onUploadAvatar={async (file) => {
        return await uploadAvatar(file)
      }}
      onUpdateEmail={async (email) => {
        await updateEmail(email)
      }}
      onUpdatePassword={async (current, newPassword) => {
        await changePassword(current, newPassword)
      }}
      onToggleMFA={async (enabled) => {
        await toggleMFA(enabled)
      }}
      showSecurityTab={true}
      showDangerZone={true}
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `user`: User data (required)
- `onUpdateProfile?`: Callback to update profile information
- `onUploadAvatar?`: Callback to upload avatar
- `onUpdateEmail?`: Callback to update email address
- `onUpdatePassword?`: Callback to change password
- `onToggleMFA?`: Callback to enable/disable MFA
- `onDeleteAccount?`: Callback to delete account
- `onError?`: Callback on error
- `showSecurityTab?`: Show security tab (default: `true`)
- `showDangerZone?`: Show danger zone (default: `true`)

**Features:**
- ✅ Three-tab interface (Profile, Security, Account)
- ✅ Profile information editing (name, username, phone)
- ✅ Avatar upload with preview
- ✅ Email update with verification status
- ✅ Password change with validation
- ✅ MFA enable/disable toggle
- ✅ Account deletion with confirmation
- ✅ Comprehensive account information display

---

### PasswordReset

Complete password reset flow component with multi-step process.

```tsx
import { PasswordReset } from '@plinto/ui'

function ResetPasswordPage() {
  return (
    <PasswordReset
      onRequestReset={async (email) => {
        await requestPasswordReset(email)
      }}
      onResetPassword={async (token, newPassword) => {
        await resetPassword(token, newPassword)
      }}
      onBackToSignIn={() => {
        navigate('/sign-in')
      }}
      logoUrl="/logo.png"
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `step?`: Current step (`'request'` | `'verify'` | `'reset'` | `'success'`)
- `email?`: Email address for password reset
- `token?`: Reset token from email link
- `onRequestReset?`: Callback to request password reset
- `onVerifyToken?`: Callback to verify reset token
- `onResetPassword?`: Callback to reset password
- `onError?`: Callback on error
- `onBackToSignIn?`: Callback to navigate back to sign in
- `logoUrl?`: Custom logo URL

**Features:**
- ✅ Four-step flow (request → verify → reset → success)
- ✅ Email input with validation
- ✅ Password strength meter
- ✅ Token verification from email link
- ✅ New password confirmation
- ✅ Success state with redirect
- ✅ Error handling with retry options

---

### EmailVerification

Email verification component with automatic token verification.

```tsx
import { EmailVerification } from '@plinto/ui'

function VerifyEmailPage() {
  const token = new URLSearchParams(window.location.search).get('token')

  return (
    <EmailVerification
      email="user@example.com"
      token={token}
      onVerify={async (token) => {
        await verifyEmail(token)
      }}
      onResendEmail={async () => {
        await resendVerificationEmail()
      }}
      onComplete={() => {
        navigate('/dashboard')
      }}
      showResend={true}
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `email`: Email address being verified (required)
- `status?`: Current verification status (`'pending'` | `'verifying'` | `'success'` | `'error'`)
- `token?`: Verification token from email link
- `onVerify?`: Callback to verify email
- `onResendEmail?`: Callback to resend verification email
- `onError?`: Callback on error
- `onComplete?`: Callback when verification is complete
- `showResend?`: Show resend option (default: `true`)
- `logoUrl?`: Custom logo URL

**Features:**
- ✅ Automatic token verification from URL
- ✅ Four status states (pending, verifying, success, error)
- ✅ Resend email with cooldown timer
- ✅ Email sent confirmation
- ✅ Success state with callback
- ✅ Error state with retry options
- ✅ Helpful troubleshooting tips

---

### PhoneVerification

SMS verification component with two-step flow.

```tsx
import { PhoneVerification } from '@plinto/ui'

function VerifyPhonePage() {
  return (
    <PhoneVerification
      phoneNumber="+1 (555) 123-4567"
      onSendCode={async (phoneNumber) => {
        await sendVerificationSMS(phoneNumber)
      }}
      onVerifyCode={async (code) => {
        await verifyPhoneCode(code)
      }}
      onComplete={() => {
        navigate('/dashboard')
      }}
    />
  )
}
```

**Props:**
- `className?`: Optional custom class name
- `phoneNumber`: Phone number being verified (required)
- `step?`: Current step (`'send'` | `'verify'` | `'success'`)
- `onSendCode?`: Callback to send verification code
- `onVerifyCode?`: Callback to verify code
- `onError?`: Callback on error
- `onComplete?`: Callback when verification is complete
- `logoUrl?`: Custom logo URL

**Features:**
- ✅ Two-step flow (send code → verify code → success)
- ✅ Phone number input with formatting
- ✅ 6-digit code input with auto-submit
- ✅ Resend code with cooldown timer
- ✅ Change phone number option
- ✅ Attempt tracking with help after failures
- ✅ Success state with callback

---

## 🎯 Roadmap

**Phase 1 (Completed):** ✅
- ✅ SignIn component
- ✅ SignUp component
- ✅ UserButton component
- ✅ MFASetup component
- ✅ MFAChallenge component
- ✅ BackupCodes component
- ✅ OrganizationSwitcher component
- ✅ OrganizationProfile component
- ✅ UserProfile component
- ✅ PasswordReset component
- ✅ EmailVerification component
- ✅ PhoneVerification component

**Phase 2 (Coming Soon):**
- 🔄 SessionManagement component
- 🔄 DeviceManagement component
- 🔄 AuditLog component

**Phase 3 (Future):**
- 🔄 InviteMembers component (standalone)
- 🔄 SSOConfiguration component
- 🔄 ComplianceDashboard component

## 📦 Package Info

**Current Version:** 1.0.0
**License:** MIT
**Bundle Size:** ~45KB (gzipped)

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines for more information.

## 📄 License

MIT © Plinto
