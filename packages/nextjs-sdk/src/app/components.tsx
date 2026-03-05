'use client';

import React from 'react';
import { useAuth, useUser as _useUser } from './provider';
import {
  SignIn as UISignIn,
  SignUp as UISignUp,
  UserButton as UIUserButton,
} from '@janua/ui/components/auth';
import type { SignInProps as UISignInProps } from '@janua/ui/components/auth';
import type { SignUpProps as UISignUpProps } from '@janua/ui/components/auth';
import type { UserButtonProps as UIUserButtonProps } from '@janua/ui/components/auth';

// SignIn Component - thin wrapper around @janua/ui SignIn
export interface SignInFormProps {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
  redirectTo?: string;
  className?: string;
  /** Pass-through props to @janua/ui SignIn */
  appearance?: UISignInProps['appearance'];
  socialProviders?: UISignInProps['socialProviders'];
  logoUrl?: string;
  showRememberMe?: boolean;
  signUpUrl?: string;
  layout?: UISignInProps['layout'];
  enablePasskey?: boolean;
  enableSSO?: boolean;
  enableMagicLink?: boolean;
  enableJanuaSSO?: boolean;
  onMFARequired?: (session: any) => void;
  headerText?: string;
  headerDescription?: string;
  forgotPasswordUrl?: string;
}

export function SignInForm({
  onSuccess,
  onError,
  redirectTo = '/',
  className,
  appearance,
  socialProviders,
  logoUrl,
  showRememberMe,
  signUpUrl,
  layout,
  enablePasskey,
  enableSSO,
  enableMagicLink,
  enableJanuaSSO,
  onMFARequired,
  headerText,
  headerDescription,
  forgotPasswordUrl,
}: SignInFormProps) {
  const { auth } = useAuth();

  return (
    <UISignIn
      className={className}
      januaClient={{ auth }}
      afterSignIn={onSuccess ? () => onSuccess() : undefined}
      onError={onError}
      redirectUrl={redirectTo}
      appearance={appearance}
      socialProviders={socialProviders}
      logoUrl={logoUrl}
      showRememberMe={showRememberMe}
      signUpUrl={signUpUrl}
      layout={layout}
      enablePasskey={enablePasskey}
      enableSSO={enableSSO}
      enableMagicLink={enableMagicLink}
      enableJanuaSSO={enableJanuaSSO}
      onMFARequired={onMFARequired}
      headerText={headerText}
      headerDescription={headerDescription}
      forgotPasswordUrl={forgotPasswordUrl}
    />
  );
}

/** Modern alias for SignInForm */
export const SignIn = SignInForm;

// SignUp Component - thin wrapper around @janua/ui SignUp
export interface SignUpFormProps {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
  redirectTo?: string;
  className?: string;
  includeNames?: boolean;
  /** Pass-through props to @janua/ui SignUp */
  appearance?: UISignUpProps['appearance'];
  socialProviders?: UISignUpProps['socialProviders'];
  logoUrl?: string;
  signInUrl?: string;
  layout?: UISignUpProps['layout'];
  requireEmailVerification?: boolean;
  showPasswordStrength?: boolean;
  termsUrl?: string;
  privacyUrl?: string;
}

export function SignUpForm({
  onSuccess,
  onError,
  redirectTo = '/',
  className,
  appearance,
  socialProviders,
  logoUrl,
  signInUrl,
  layout,
  requireEmailVerification,
  showPasswordStrength,
  termsUrl,
  privacyUrl,
}: SignUpFormProps) {
  const { auth } = useAuth();

  return (
    <UISignUp
      className={className}
      januaClient={{ auth }}
      afterSignUp={onSuccess ? () => onSuccess() : undefined}
      onError={onError}
      redirectUrl={redirectTo}
      appearance={appearance}
      socialProviders={socialProviders}
      logoUrl={logoUrl}
      signInUrl={signInUrl}
      layout={layout}
      requireEmailVerification={requireEmailVerification}
      showPasswordStrength={showPasswordStrength}
      termsUrl={termsUrl}
      privacyUrl={privacyUrl}
    />
  );
}

/** Modern alias for SignUpForm */
export const SignUp = SignUpForm;

// UserButton Component - thin wrapper around @janua/ui UserButton
export interface UserButtonProps {
  className?: string;
  showEmail?: boolean;
  showName?: boolean;
  afterSignOut?: () => void;
  showManageAccount?: boolean;
  manageAccountUrl?: string;
  showOrganizations?: boolean;
  activeOrganization?: string;
}

export function UserButton({
  className,
  afterSignOut,
  showManageAccount,
  manageAccountUrl,
  showOrganizations,
  activeOrganization,
}: UserButtonProps) {
  const { user, signOut } = useAuth();

  if (!user) {
    return null;
  }

  const handleSignOut = async () => {
    await signOut();
    if (afterSignOut) {
      afterSignOut();
    }
  };

  return (
    <UIUserButton
      className={className}
      user={{
        id: user.id,
        email: user.email,
        firstName: user.first_name,
        lastName: user.last_name,
        avatarUrl: user.profile_image_url,
      }}
      onSignOut={handleSignOut}
      showManageAccount={showManageAccount}
      manageAccountUrl={manageAccountUrl}
      showOrganizations={showOrganizations}
      activeOrganization={activeOrganization}
    />
  );
}

// SignedIn Component - pure React logic, no UI dependency needed
export interface SignedInProps {
  children: React.ReactNode;
}

export function SignedIn({ children }: SignedInProps) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}

// SignedOut Component
export interface SignedOutProps {
  children: React.ReactNode;
}

export function SignedOut({ children }: SignedOutProps) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}

// RedirectToSignIn Component
export interface RedirectToSignInProps {
  redirectUrl?: string;
}

export function RedirectToSignIn({ redirectUrl = '/login' }: RedirectToSignInProps) {
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      const currentPath = window.location.pathname;
      const url = new URL(redirectUrl, window.location.origin);
      url.searchParams.set('from', currentPath);
      window.location.href = url.toString();
    }
  }, [redirectUrl]);

  return null;
}

// Protect Component
export interface ProtectProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  redirectTo?: string;
}

export function Protect({ children, fallback, redirectTo }: ProtectProps) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <>{fallback || <div>Loading...</div>}</>;
  }

  if (!isAuthenticated) {
    if (redirectTo) {
      return <RedirectToSignIn redirectUrl={redirectTo} />;
    }
    return <>{fallback || null}</>;
  }

  return <>{children}</>;
}
