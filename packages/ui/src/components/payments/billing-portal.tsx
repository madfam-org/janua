/**
 * Billing Portal Component
 *
 * Unified dashboard for complete billing and subscription management.
 *
 * Features:
 * - Tab navigation (Subscription, Payment Methods, Invoices)
 * - Summary cards (active plan, next billing, total spent)
 * - Quick actions (add payment method, upgrade plan, view invoices)
 * - Responsive layout
 * - Integration of all payment components
 */

'use client';

import { useState } from 'react';
import { SubscriptionManagement } from './subscription-management';
import { PaymentMethodForm } from './payment-method-form';
import { InvoiceList } from './invoice-list';
import { SubscriptionPlans } from './subscription-plans';

export interface BillingPortalProps {
  /**
   * Plinto client instance
   */
  client: any;

  /**
   * Initial tab to display
   */
  initialTab?: 'subscription' | 'payment-methods' | 'invoices' | 'plans';

  /**
   * Custom styling
   */
  className?: string;
}

type Tab = 'subscription' | 'payment-methods' | 'invoices' | 'plans';

export function BillingPortal({
  client,
  initialTab = 'subscription',
  className = '',
}: BillingPortalProps) {
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  const [showAddPaymentMethod, setShowAddPaymentMethod] = useState(false);

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: 'subscription', label: 'Subscription', icon: '📋' },
    { id: 'payment-methods', label: 'Payment Methods', icon: '💳' },
    { id: 'invoices', label: 'Invoices', icon: '📄' },
    { id: 'plans', label: 'Plans', icon: '📦' },
  ];

  const handlePaymentMethodAdded = () => {
    setShowAddPaymentMethod(false);
    // Optionally switch to payment methods tab to show the new method
    setActiveTab('payment-methods');
  };

  return (
    <div className={`max-w-7xl mx-auto ${className}`}>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Billing Portal</h1>
        <p className="mt-2 text-sm text-gray-600">
          Manage your subscription, payment methods, and invoices
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm
                ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {/* Subscription Tab */}
        {activeTab === 'subscription' && (
          <div className="space-y-6">
            <SubscriptionManagement client={client} />
          </div>
        )}

        {/* Payment Methods Tab */}
        {activeTab === 'payment-methods' && (
          <div className="space-y-6">
            {!showAddPaymentMethod ? (
              <>
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-gray-900">Payment Methods</h2>
                  <button
                    onClick={() => setShowAddPaymentMethod(true)}
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                  >
                    Add Payment Method
                  </button>
                </div>

                <PaymentMethodsList client={client} />
              </>
            ) : (
              <PaymentMethodForm
                client={client}
                onSuccess={handlePaymentMethodAdded}
                onCancel={() => setShowAddPaymentMethod(false)}
              />
            )}
          </div>
        )}

        {/* Invoices Tab */}
        {activeTab === 'invoices' && (
          <div className="space-y-6">
            <InvoiceList client={client} />
          </div>
        )}

        {/* Plans Tab */}
        {activeTab === 'plans' && (
          <div className="space-y-6">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-gray-900">Available Plans</h2>
              <p className="mt-1 text-sm text-gray-600">
                Choose a plan that fits your needs or upgrade your current subscription
              </p>
            </div>
            <SubscriptionPlans
              client={client}
              onSelectPlan={(planId, interval) => {
                // Handle plan selection - could navigate to checkout or show confirmation
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Payment Methods List Component
 * (Simple component for displaying payment methods)
 */
function PaymentMethodsList({ client }: { client: any }) {
  const [paymentMethods, setPaymentMethods] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadPaymentMethods = async () => {
    try {
      setLoading(true);
      setError(null);
      const methods = await client.payments.listPaymentMethods();
      setPaymentMethods(methods);
    } catch (err: any) {
      setError(err.message || 'Failed to load payment methods');
    } finally {
      setLoading(false);
    }
  };

  const handleSetDefault = async (methodId: string) => {
    try {
      setActionLoading(methodId);
      await client.payments.setDefaultPaymentMethod(methodId);
      await loadPaymentMethods();
    } catch (err: any) {
      setError(err.message || 'Failed to set default payment method');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (methodId: string) => {
    if (!confirm('Are you sure you want to delete this payment method?')) return;

    try {
      setActionLoading(methodId);
      await client.payments.deletePaymentMethod(methodId);
      await loadPaymentMethods();
    } catch (err: any) {
      setError(err.message || 'Failed to delete payment method');
    } finally {
      setActionLoading(null);
    }
  };

  React.useEffect(() => {
    loadPaymentMethods();
  }, [client]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md bg-red-50 p-4">
        <p className="text-sm text-red-800">{error}</p>
      </div>
    );
  }

  if (paymentMethods.length === 0) {
    return (
      <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900">No payment methods</h3>
        <p className="mt-1 text-sm text-gray-500">
          Add a payment method to start your subscription
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {paymentMethods.map((method) => (
        <div
          key={method.id}
          className="relative bg-white rounded-lg border border-gray-200 p-4"
        >
          {method.is_default && (
            <div className="absolute top-2 right-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                Default
              </span>
            </div>
          )}

          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <svg className="h-8 w-8 text-gray-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                </svg>
                <div>
                  <div className="text-sm font-medium text-gray-900">
                    {method.brand} •••• {method.last4}
                  </div>
                  <div className="text-xs text-gray-500">
                    Expires {method.exp_month}/{method.exp_year}
                  </div>
                </div>
              </div>

              <div className="mt-2 text-xs text-gray-500">
                Provider:{' '}
                <span className="font-medium">
                  {method.provider.charAt(0).toUpperCase() + method.provider.slice(1)}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 flex gap-2">
            {!method.is_default && (
              <button
                onClick={() => handleSetDefault(method.id)}
                disabled={actionLoading === method.id}
                className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-400"
              >
                Set as Default
              </button>
            )}
            <button
              onClick={() => handleDelete(method.id)}
              disabled={actionLoading === method.id}
              className="text-sm text-red-600 hover:text-red-800 disabled:text-gray-400"
            >
              Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
