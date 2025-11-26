/**
 * Polar Checkout Button Component
 *
 * A pre-styled button that initiates Polar checkout for subscription purchases.
 * Handles loading states, error handling, and redirects to Polar checkout.
 *
 * @example
 * ```tsx
 * <PolarCheckoutButton
 *   plan="pro"
 *   organizationId="org_123"
 *   successUrl="/dashboard?upgraded=true"
 * >
 *   Upgrade to Pro
 * </PolarCheckoutButton>
 * ```
 */

'use client';

import * as React from 'react';
import { useState, useCallback } from 'react';
import { cn } from '../../lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface PolarCheckoutButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /**
   * Plan name (must be configured in Polar plugin)
   */
  plan?: string;

  /**
   * Direct Polar product ID (alternative to plan)
   */
  productId?: string;

  /**
   * Polar price ID for specific pricing tier
   */
  priceId?: string;

  /**
   * Organization ID to associate subscription with
   */
  organizationId: string;

  /**
   * URL to redirect after successful checkout
   */
  successUrl?: string;

  /**
   * URL to redirect if user cancels
   */
  cancelUrl?: string;

  /**
   * Customer email for guest checkout
   */
  email?: string;

  /**
   * Additional metadata
   */
  metadata?: Record<string, string>;

  /**
   * Button variant
   */
  variant?: 'default' | 'primary' | 'secondary' | 'outline' | 'ghost';

  /**
   * Button size
   */
  size?: 'sm' | 'md' | 'lg' | 'xl';

  /**
   * Show loading spinner
   */
  loading?: boolean;

  /**
   * Custom loading text
   */
  loadingText?: string;

  /**
   * Callback when checkout starts
   */
  onCheckoutStart?: () => void;

  /**
   * Callback when checkout fails
   */
  onCheckoutError?: (error: Error) => void;

  /**
   * Janua client instance (if not using context)
   */
  client?: any;

  /**
   * Button content
   */
  children?: React.ReactNode;
}

// ============================================================================
// Component
// ============================================================================

export const PolarCheckoutButton = React.forwardRef<
  HTMLButtonElement,
  PolarCheckoutButtonProps
>(
  (
    {
      plan,
      productId,
      priceId,
      organizationId,
      successUrl,
      cancelUrl,
      email,
      metadata,
      variant = 'primary',
      size = 'md',
      loading: externalLoading,
      loadingText = 'Loading...',
      onCheckoutStart,
      onCheckoutError,
      client,
      children = 'Subscribe',
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const [internalLoading, setInternalLoading] = useState(false);
    const isLoading = externalLoading || internalLoading;

    const handleCheckout = useCallback(async () => {
      if (!client?.polar) {
        const error = new Error('Polar plugin not initialized. Make sure to install the Polar plugin on your Janua client.');
        onCheckoutError?.(error);
        console.error(error);
        return;
      }

      if (!plan && !productId) {
        const error = new Error('Either plan or productId is required');
        onCheckoutError?.(error);
        console.error(error);
        return;
      }

      setInternalLoading(true);
      onCheckoutStart?.();

      try {
        await client.polar.checkout({
          plan,
          productId,
          priceId,
          organizationId,
          successUrl,
          cancelUrl,
          email,
          metadata
        });
      } catch (error) {
        setInternalLoading(false);
        onCheckoutError?.(error as Error);
        console.error('Polar checkout error:', error);
      }
    }, [
      client,
      plan,
      productId,
      priceId,
      organizationId,
      successUrl,
      cancelUrl,
      email,
      metadata,
      onCheckoutStart,
      onCheckoutError
    ]);

    // Variant styles
    const variantStyles = {
      default: 'bg-gray-900 text-white hover:bg-gray-800 dark:bg-gray-50 dark:text-gray-900 dark:hover:bg-gray-200',
      primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
      secondary: 'bg-gray-600 text-white hover:bg-gray-700 focus:ring-gray-500',
      outline: 'border-2 border-blue-600 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950 focus:ring-blue-500',
      ghost: 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
    };

    // Size styles
    const sizeStyles = {
      sm: 'px-3 py-1.5 text-sm rounded',
      md: 'px-4 py-2 text-base rounded-md',
      lg: 'px-6 py-3 text-lg rounded-lg',
      xl: 'px-8 py-4 text-xl rounded-xl'
    };

    return (
      <button
        ref={ref}
        type="button"
        onClick={handleCheckout}
        disabled={disabled || isLoading}
        className={cn(
          // Base styles
          'inline-flex items-center justify-center font-medium transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-offset-2',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          // Variant
          variantStyles[variant],
          // Size
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {isLoading ? (
          <>
            <svg
              className="animate-spin -ml-1 mr-2 h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            {loadingText}
          </>
        ) : (
          children
        )}
      </button>
    );
  }
);

PolarCheckoutButton.displayName = 'PolarCheckoutButton';

export default PolarCheckoutButton;
