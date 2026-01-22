/**
 * Subscription Plans Component
 *
 * Display and select subscription plans with pricing and features.
 * Supports multi-provider payment infrastructure.
 */

'use client';

import { useState, useEffect } from 'react';
import type { SubscriptionPlan, BillingInterval } from '@janua/typescript-sdk';

export interface SubscriptionPlansProps {
  /**
   * Janua client instance
   */
  client: any;

  /**
   * Selected billing interval (monthly/yearly)
   */
  billingInterval?: BillingInterval;

  /**
   * Callback when plan is selected
   */
  onSelectPlan?: (planId: string, interval: BillingInterval) => void;

  /**
   * Custom styling
   */
  className?: string;
}

export function SubscriptionPlans({
  client,
  billingInterval = 'monthly',
  onSelectPlan,
  className = '',
}: SubscriptionPlansProps) {
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [selectedInterval, setSelectedInterval] = useState<BillingInterval>(billingInterval);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPlans();
  }, [client]);

  const loadPlans = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await client.payments.listPlans();
      setPlans(data.filter((p: SubscriptionPlan) => p.is_active));
    } catch (err: any) {
      setError(err.message || 'Failed to load subscription plans');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPlan = (planId: string) => {
    if (onSelectPlan) {
      onSelectPlan(planId, selectedInterval);
    }
  };

  const getPrice = (plan: SubscriptionPlan) => {
    return selectedInterval === 'monthly' ? plan.price_monthly : plan.price_yearly;
  };

  const getPriceDisplay = (plan: SubscriptionPlan) => {
    const price = getPrice(plan);
    if (price === null || price === undefined) return 'Custom pricing';

    const _currency = plan.currency_usd; // Default to USD, can detect user locale
    return `$${price.toFixed(2)}/${selectedInterval === 'monthly' ? 'mo' : 'yr'}`;
  };

  if (loading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`rounded-lg bg-red-50 p-4 ${className}`}>
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Error loading plans</h3>
            <p className="mt-2 text-sm text-red-700">{error}</p>
            <button
              onClick={loadPlans}
              className="mt-3 text-sm font-medium text-red-800 hover:text-red-900"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Billing Interval Toggle */}
      <div className="flex justify-center mb-8">
        <div className="inline-flex rounded-lg border border-gray-200 p-1">
          <button
            onClick={() => setSelectedInterval('monthly')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              selectedInterval === 'monthly'
                ? 'bg-blue-600 text-white'
                : 'text-gray-700 hover:text-gray-900'
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => setSelectedInterval('yearly')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              selectedInterval === 'yearly'
                ? 'bg-blue-600 text-white'
                : 'text-gray-700 hover:text-gray-900'
            }`}
          >
            Yearly
            <span className="ml-1 text-xs">(Save 20%)</span>
          </button>
        </div>
      </div>

      {/* Plans Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {plans.map((plan) => (
          <div
            key={plan.id}
            className="relative rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
          >
            {/* Plan Header */}
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-gray-900">{plan.name}</h3>
              {plan.description && (
                <p className="mt-1 text-sm text-gray-600">{plan.description}</p>
              )}
            </div>

            {/* Pricing */}
            <div className="mb-6">
              <div className="text-3xl font-bold text-gray-900">{getPriceDisplay(plan)}</div>
            </div>

            {/* Features List */}
            <ul className="mb-6 space-y-3">
              {plan.features.map((feature, index) => (
                <li key={index} className="flex items-start">
                  <svg
                    className="h-5 w-5 text-green-500 mr-2 flex-shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="text-sm text-gray-700">{feature}</span>
                </li>
              ))}
            </ul>

            {/* Limits Display */}
            {Object.keys(plan.limits).length > 0 && (
              <div className="mb-6 pt-4 border-t border-gray-200">
                <h4 className="text-xs font-semibold text-gray-900 uppercase tracking-wide mb-2">
                  Plan Limits
                </h4>
                <ul className="space-y-1">
                  {Object.entries(plan.limits).map(([key, value]) => (
                    <li key={key} className="text-sm text-gray-600">
                      {key.replace(/_/g, ' ')}: <span className="font-medium">{value}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Select Button */}
            <button
              onClick={() => handleSelectPlan(plan.id)}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              Select Plan
            </button>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {plans.length === 0 && (
        <div className="text-center py-12">
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
              d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No plans available</h3>
          <p className="mt-1 text-sm text-gray-500">
            There are currently no subscription plans available.
          </p>
        </div>
      )}
    </div>
  );
}
