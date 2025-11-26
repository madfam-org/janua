/**
 * Polar Subscription Status Component
 *
 * Displays current subscription status with plan information,
 * renewal date, and quick actions for management.
 *
 * @example
 * ```tsx
 * <PolarSubscriptionStatus
 *   organizationId="org_123"
 *   client={januaClient}
 *   showActions
 *   onUpgrade={() => navigate('/pricing')}
 * />
 * ```
 */

'use client';

import * as React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { cn } from '../../lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface PolarSubscriptionStatusProps {
  /**
   * Organization ID
   */
  organizationId: string;

  /**
   * Janua client instance with Polar plugin
   */
  client: any;

  /**
   * Show action buttons (cancel, resume, upgrade)
   */
  showActions?: boolean;

  /**
   * Show cancel button
   */
  showCancelButton?: boolean;

  /**
   * Compact display mode
   */
  compact?: boolean;

  /**
   * Callback when subscription changes
   */
  onSubscriptionChange?: (subscription: Subscription | null) => void;

  /**
   * Callback when cancel is requested
   */
  onCancel?: () => void;

  /**
   * Callback when upgrade is requested
   */
  onUpgrade?: () => void;

  /**
   * Callback on error
   */
  onError?: (error: Error) => void;

  /**
   * Additional CSS classes
   */
  className?: string;
}

interface Subscription {
  id: string;
  status: 'incomplete' | 'trialing' | 'active' | 'past_due' | 'canceled' | 'unpaid';
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
  canceledAt?: string;
  plan?: string;
  productId: string;
}

// ============================================================================
// Component
// ============================================================================

export function PolarSubscriptionStatus({
  organizationId,
  client,
  showActions = false,
  showCancelButton = true,
  compact = false,
  onSubscriptionChange,
  onCancel,
  onUpgrade,
  onError,
  className
}: PolarSubscriptionStatusProps) {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    loadSubscription();
  }, [organizationId]);

  const loadSubscription = async () => {
    if (!client?.polar) {
      setLoading(false);
      return;
    }

    try {
      const sub = await client.polar.getSubscription(organizationId);
      setSubscription(sub);
      onSubscriptionChange?.(sub);
    } catch (error) {
      console.error('Failed to load subscription:', error);
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = useCallback(async () => {
    if (!subscription || !client?.polar) return;

    const confirmed = window.confirm(
      'Are you sure you want to cancel your subscription? You will retain access until the end of your billing period.'
    );

    if (!confirmed) return;

    setActionLoading('cancel');

    try {
      const updated = await client.polar.cancelSubscription(subscription.id, true);
      setSubscription(updated);
      onSubscriptionChange?.(updated);
      onCancel?.();
    } catch (error) {
      console.error('Failed to cancel subscription:', error);
      onError?.(error as Error);
    } finally {
      setActionLoading(null);
    }
  }, [subscription, client, onSubscriptionChange, onCancel, onError]);

  const handleResume = useCallback(async () => {
    if (!subscription || !client?.polar) return;

    setActionLoading('resume');

    try {
      const updated = await client.polar.resumeSubscription(subscription.id);
      setSubscription(updated);
      onSubscriptionChange?.(updated);
    } catch (error) {
      console.error('Failed to resume subscription:', error);
      onError?.(error as Error);
    } finally {
      setActionLoading(null);
    }
  }, [subscription, client, onSubscriptionChange, onError]);

  // Loading state
  if (loading) {
    return (
      <div className={cn('animate-pulse', className)}>
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-24 mb-2" />
        <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-32" />
      </div>
    );
  }

  // No subscription
  if (!subscription) {
    return (
      <div className={cn('text-sm', className)}>
        <div className="flex items-center gap-2">
          <StatusDot status="none" />
          <span className="text-gray-500 dark:text-gray-400">No active subscription</span>
        </div>
        {showActions && onUpgrade && (
          <button
            onClick={onUpgrade}
            className="mt-2 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 font-medium"
          >
            Upgrade now →
          </button>
        )}
      </div>
    );
  }

  // Format dates
  const periodEnd = new Date(subscription.currentPeriodEnd);
  const daysRemaining = Math.ceil((periodEnd.getTime() - Date.now()) / (1000 * 60 * 60 * 24));

  // Compact mode
  if (compact) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <StatusDot status={subscription.status} />
        <span className="text-sm font-medium capitalize">
          {subscription.plan || 'Subscription'}
        </span>
        <StatusBadge status={subscription.status} size="sm" />
      </div>
    );
  }

  // Full display
  return (
    <div className={cn('space-y-4', className)}>
      {/* Status Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <StatusDot status={subscription.status} size="lg" />
            <h4 className="text-lg font-semibold text-gray-900 dark:text-gray-100 capitalize">
              {subscription.plan || 'Current Plan'}
            </h4>
            <StatusBadge status={subscription.status} />
          </div>
          {subscription.cancelAtPeriodEnd && (
            <p className="mt-1 text-sm text-yellow-600 dark:text-yellow-400">
              Cancels on {periodEnd.toLocaleDateString()}
            </p>
          )}
        </div>
      </div>

      {/* Details */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-gray-500 dark:text-gray-400">
            {subscription.cancelAtPeriodEnd ? 'Access until' : 'Renews'}
          </span>
          <p className="font-medium text-gray-900 dark:text-gray-100">
            {periodEnd.toLocaleDateString(undefined, {
              month: 'long',
              day: 'numeric',
              year: 'numeric'
            })}
          </p>
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-400">Days remaining</span>
          <p className="font-medium text-gray-900 dark:text-gray-100">
            {daysRemaining} {daysRemaining === 1 ? 'day' : 'days'}
          </p>
        </div>
      </div>

      {/* Warning for expiring subscriptions */}
      {subscription.cancelAtPeriodEnd && (
        <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            Your subscription is set to cancel. You'll lose access to premium features on{' '}
            {periodEnd.toLocaleDateString()}.
          </p>
        </div>
      )}

      {/* Past due warning */}
      {subscription.status === 'past_due' && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-800 dark:text-red-200">
            Your payment is past due. Please update your payment method to avoid service interruption.
          </p>
        </div>
      )}

      {/* Actions */}
      {showActions && (
        <div className="flex flex-wrap gap-2 pt-2">
          {subscription.cancelAtPeriodEnd ? (
            <button
              onClick={handleResume}
              disabled={actionLoading === 'resume'}
              className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 disabled:opacity-50"
            >
              {actionLoading === 'resume' ? (
                <>
                  <LoadingSpinner className="mr-1.5" />
                  Resuming...
                </>
              ) : (
                'Resume subscription'
              )}
            </button>
          ) : (
            <>
              {showCancelButton && subscription.status === 'active' && (
                <button
                  onClick={handleCancel}
                  disabled={actionLoading === 'cancel'}
                  className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50"
                >
                  {actionLoading === 'cancel' ? (
                    <>
                      <LoadingSpinner className="mr-1.5" />
                      Canceling...
                    </>
                  ) : (
                    'Cancel subscription'
                  )}
                </button>
              )}
              {onUpgrade && (
                <button
                  onClick={onUpgrade}
                  className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 hover:text-blue-700"
                >
                  Upgrade plan →
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

interface StatusDotProps {
  status: string;
  size?: 'sm' | 'lg';
}

function StatusDot({ status, size = 'sm' }: StatusDotProps) {
  const colors: Record<string, string> = {
    active: 'bg-green-500',
    trialing: 'bg-blue-500',
    past_due: 'bg-yellow-500',
    canceled: 'bg-red-500',
    unpaid: 'bg-red-500',
    incomplete: 'bg-gray-500',
    none: 'bg-gray-300'
  };

  const sizeClasses = size === 'lg' ? 'h-3 w-3' : 'h-2 w-2';

  return (
    <span
      className={cn(
        'inline-block rounded-full',
        sizeClasses,
        colors[status] || colors.none
      )}
    />
  );
}

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    active: {
      bg: 'bg-green-100 dark:bg-green-900/30',
      text: 'text-green-800 dark:text-green-300',
      label: 'Active'
    },
    trialing: {
      bg: 'bg-blue-100 dark:bg-blue-900/30',
      text: 'text-blue-800 dark:text-blue-300',
      label: 'Trial'
    },
    past_due: {
      bg: 'bg-yellow-100 dark:bg-yellow-900/30',
      text: 'text-yellow-800 dark:text-yellow-300',
      label: 'Past Due'
    },
    canceled: {
      bg: 'bg-red-100 dark:bg-red-900/30',
      text: 'text-red-800 dark:text-red-300',
      label: 'Canceled'
    },
    unpaid: {
      bg: 'bg-red-100 dark:bg-red-900/30',
      text: 'text-red-800 dark:text-red-300',
      label: 'Unpaid'
    },
    incomplete: {
      bg: 'bg-gray-100 dark:bg-gray-800',
      text: 'text-gray-800 dark:text-gray-300',
      label: 'Incomplete'
    }
  };

  const { bg, text, label } = config[status] || config.incomplete;
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-0.5 text-xs';

  return (
    <span className={cn('inline-flex items-center rounded-full font-medium', bg, text, sizeClasses)}>
      {label}
    </span>
  );
}

function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn('animate-spin h-4 w-4', className)}
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
  );
}

export default PolarSubscriptionStatus;
