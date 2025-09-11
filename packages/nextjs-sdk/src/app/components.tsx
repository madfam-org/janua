'use client';

import React, { useState } from 'react';
import { useAuth, useUser } from './provider';
import type { SignUpRequest, SignInRequest } from '@plinto/js';

// SignIn Component
export interface SignInFormProps {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
  redirectTo?: string;
  className?: string;
}

export function SignInForm({ 
  onSuccess, 
  onError, 
  redirectTo = '/',
  className 
}: SignInFormProps) {
  const { auth } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await auth.signIn({ email, password });
      if (onSuccess) {
        onSuccess();
      } else if (typeof window !== 'undefined') {
        window.location.href = redirectTo;
      }
    } catch (error) {
      if (onError) {
        onError(error as Error);
      } else {
        console.error('Sign in failed:', error);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={className}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        required
        disabled={isLoading}
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        required
        disabled={isLoading}
      />
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Signing in...' : 'Sign In'}
      </button>
    </form>
  );
}

// SignUp Component
export interface SignUpFormProps {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
  redirectTo?: string;
  className?: string;
  includeNames?: boolean;
}

export function SignUpForm({ 
  onSuccess, 
  onError, 
  redirectTo = '/',
  className,
  includeNames = true
}: SignUpFormProps) {
  const { auth } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState<SignUpRequest>({
    email: '',
    password: '',
    firstName: '',
    lastName: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await auth.signUp(formData);
      if (onSuccess) {
        onSuccess();
      } else if (typeof window !== 'undefined') {
        window.location.href = redirectTo;
      }
    } catch (error) {
      if (onError) {
        onError(error as Error);
      } else {
        console.error('Sign up failed:', error);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={className}>
      {includeNames && (
        <>
          <input
            type="text"
            value={formData.firstName || ''}
            onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
            placeholder="First Name"
            disabled={isLoading}
          />
          <input
            type="text"
            value={formData.lastName || ''}
            onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
            placeholder="Last Name"
            disabled={isLoading}
          />
        </>
      )}
      <input
        type="email"
        value={formData.email}
        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
        placeholder="Email"
        required
        disabled={isLoading}
      />
      <input
        type="password"
        value={formData.password}
        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
        placeholder="Password"
        required
        disabled={isLoading}
      />
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Creating account...' : 'Sign Up'}
      </button>
    </form>
  );
}

// UserButton Component
export interface UserButtonProps {
  className?: string;
  showEmail?: boolean;
  showName?: boolean;
  afterSignOut?: () => void;
}

export function UserButton({ 
  className,
  showEmail = true,
  showName = true,
  afterSignOut
}: UserButtonProps) {
  const { user, signOut } = useAuth();
  const [isOpen, setIsOpen] = useState(false);

  if (!user) {
    return null;
  }

  const handleSignOut = async () => {
    await signOut();
    if (afterSignOut) {
      afterSignOut();
    }
  };

  const displayName = showName && (user.firstName || user.lastName)
    ? `${user.firstName || ''} ${user.lastName || ''}`.trim()
    : null;

  return (
    <div className={className} style={{ position: 'relative' }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px',
          border: '1px solid #ccc',
          borderRadius: '8px',
          background: 'white',
          cursor: 'pointer',
        }}
      >
        {user.profileImageUrl ? (
          <img
            src={user.profileImageUrl}
            alt="Profile"
            style={{ width: 32, height: 32, borderRadius: '50%' }}
          />
        ) : (
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              background: '#ccc',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {user.email[0].toUpperCase()}
          </div>
        )}
        <div style={{ textAlign: 'left' }}>
          {displayName && <div style={{ fontWeight: 500 }}>{displayName}</div>}
          {showEmail && <div style={{ fontSize: '0.875rem', color: '#666' }}>{user.email}</div>}
        </div>
      </button>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '8px',
            background: 'white',
            border: '1px solid #ccc',
            borderRadius: '8px',
            padding: '8px',
            minWidth: '200px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            zIndex: 1000,
          }}
        >
          <button
            onClick={handleSignOut}
            style={{
              width: '100%',
              padding: '8px',
              border: 'none',
              background: 'none',
              textAlign: 'left',
              cursor: 'pointer',
            }}
          >
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}

// SignedIn Component
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