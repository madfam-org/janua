/**
 * Polar Customer Portal Component
 *
 * Button and card components for accessing the Polar customer portal,
 * where users can manage their subscriptions, payment methods, and invoices.
 *
 * @example
 * ```tsx
 * // Simple button
 * <PolarCustomerPortalButton
 *   organizationId="org_123"
 *   client={januaClient}
 * />
 *
 * // Full portal card with subscription info
 * <PolarCustomerPortalCard
 *   organizationId="org_123"
 *   client={januaClient}
 *   showSubscriptionInfo
 * />
 * ```
 */

'use client';

import * as React from 'react';
import { useState, useCallback, useEffect } from 'react';
import { cn } from '../../lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface PolarCustomerPortalButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /**
   * Organization ID
   */
  organizationId: string;

  /**
   * Janua client instance
   */
  client: any;

  /**
   * Button variant
   */
  variant?: 'default' | 'primary' | 'secondary' | 'outline' | 'ghost' | 'link';

  /**
   * Button size
   */
  size?: 'sm' | 'md' | 'lg';

  /**
   * Custom loading text
   */
  loadingText?: string;

  /**
   * Callback on error
   */
  onError?: (error: Error) => void;

  /**
   * Button content
   */
  children?: React.ReactNode;
}

export interface PolarCustomerPortalCardProps {
  /**
   * Organization ID
   */
  organizationId: string;

  /**
   * Janua client instance
   */
  client: any;

  /**
   * Show current subscription information
   */
  showSubscriptionInfo?: boolean;

  /**
   * Show usage summary
   */
  showUsageSummary?: boolean;

  /**
   * Custom title
   */
  title?: string;

  /**
   * Custom description
   */
  description?: string;

  /**
   * Additional CSS classes
   */
  className?: string;

  /**
   * Callback on error
   */
  onError?: (error: Error) => void;
}

interface SubscriptionInfo {
  id: string;
  status: string;
  plan?: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
}

// ============================================================================
// Portal Button Component
// ============================================================================

export const PolarCustomerPortalButton = React.forwardRef<
  HTMLButtonElement,
  PolarCustomerPortalButtonProps
>(
  (
    {
      organizationId,
      client,
      variant = 'outline',
      size = 'md',
      loadingText = 'Loading...',
      onError,
      children = 'Manage Subscription',
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const [loading, setLoading] = useState(false);

    const handlePortal = useCallback(async () => {
      if (!client?.polar) {
        const error = new Error('Polar plugin not initialized');
        onError?.(error);
        return;
      }

      setLoading(true);

      try {
        await client.polar.redirectToPortal(organizationId);
      } catch (error) {
        setLoading(false);
        onError?.(error as Error);
        console.error('Portal redirect error:', error);
      }
    }, [client, organizationId, onError]);

    // Variant styles
    const variantStyles = {
      default: 'bg-gray-900 text-white hover:bg-gray-800',
      primary: 'bg-blue-600 text-white hover:bg-blue-700',
      secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-100',
      outline: 'border border-gray-300 bg-transparent hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-800',
      ghost: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800',
      link: 'bg-transparent text-blue-600 hover:underline p-0'
    };

    // Size styles
    const sizeStyles = {
      sm: 'px-3 py-1.5 text-sm rounded',
      md: 'px-4 py-2 text-base rounded-md',
      lg: 'px-6 py-3 text-lg rounded-lg'
    };

    return (
      <button
        ref={ref}
        type="button"
        onClick={handlePortal}
        disabled={disabled || loading}
        className={cn(
          'inline-flex items-center justify-center font-medium transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          variantStyles[variant],
          variant !== 'link' && sizeStyles[size],
          className
        )}
        {...props}
      >
        {loading ? (
          <>
            <svg
              className="animate-spin -ml-1 mr-2 h-4 w-4"
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
          <>
            <ExternalLinkIcon className="mr-2 h-4 w-4" />
            {children}
          </>
        )}
      </button>
    );
  }
);

PolarCustomerPortalButton.displayName = 'PolarCustomerPortalButton';

// ============================================================================
// Portal Card Component
// ============================================================================

export function PolarCustomerPortalCard({
  organizationId,
  client,
  showSubscriptionInfo = true,
  showUsageSummary = false,
  title = 'Billing & Subscription',
  description = 'Manage your subscription, payment methods, and billing history.',
  className,
  onError
}: PolarCustomerPortalCardProps) {
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (showSubscriptionInfo && client?.polar) {
      loadSubscription();
    } else {
      setLoading(false);
    }
  }, [organizationId, client, showSubscriptionInfo]);

  const loadSubscription = async () => {
    try {
      const sub = await client.polar.getSubscription(organizationId);
      setSubscription(sub);
    } catch (error) {
      console.error('Failed to load subscription:', error);
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; label: string }> = {
      active: { color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200', label: 'Active' },
      trialing: { color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200', label: 'Trial' },
      past_due: { color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200', label: 'Past Due' },
      canceled: { color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200', label: 'Canceled' },
      unpaid: { color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200', label: 'Unpaid' }
    };

    const config = statusConfig[status] || { color: 'bg-gray-100 text-gray-800', label: status };

    return (
      <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium', config.color)}>
        {config.label}
      </span>
    );
  };

  return (
    <div
      className={cn(
        'rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-900',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {title}
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {description}
          </p>
        </div>
        <CreditCardIcon className="h-8 w-8 text-gray-400" />
      </div>

      {/* Subscription Info */}
      {showSubscriptionInfo && (
        <div className="mt-6">
          {loading ? (
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 rounded w-1/3 dark:bg-gray-700" />
              <div className="h-4 bg-gray-200 rounded w-1/2 dark:bg-gray-700" />
            </div>
          ) : subscription ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500 dark:text-gray-400">Status</span>
                {getStatusBadge(subscription.status)}
              </div>
              {subscription.plan && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500 dark:text-gray-400">Plan</span>
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100 capitalize">
                    {subscription.plan}
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {subscription.cancelAtPeriodEnd ? 'Access until' : 'Renews on'}
                </span>
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {formatDate(subscription.currentPeriodEnd)}
                </span>
              </div>
              {subscription.cancelAtPeriodEnd && (
                <div className="mt-2 p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded text-sm text-yellow-800 dark:text-yellow-200">
                  Your subscription will end on {formatDate(subscription.currentPeriodEnd)}
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-500 dark:text-gray-400">
              No active subscription
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="mt-6 flex flex-col sm:flex-row gap-3">
        <PolarCustomerPortalButton
          organizationId={organizationId}
          client={client}
          variant="outline"
          className="flex-1"
          onError={onError}
        >
          Manage Billing
        </PolarCustomerPortalButton>
      </div>

      {/* Powered by Polar */}
      <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
        <p className="text-xs text-gray-400 dark:text-gray-500 flex items-center justify-center">
          <PolarLogo className="h-3 w-3 mr-1" />
          Powered by Polar
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// Icons
// ============================================================================

function ExternalLinkIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
      />
    </svg>
  );
}

function CreditCardIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z"
      />
    </svg>
  );
}

function PolarLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <circle cx="12" cy="12" r="10" />
    </svg>
  );
}

export default PolarCustomerPortalButton;
