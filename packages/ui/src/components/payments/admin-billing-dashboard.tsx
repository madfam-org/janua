/**
 * Admin Billing Dashboard Component
 *
 * Administrative view for managing billing across all tenants/organizations.
 *
 * Features:
 * - Revenue metrics (MRR, ARR, churn rate)
 * - Subscription overview (active, trialing, past_due, canceled)
 * - Recent transactions list
 * - Provider distribution (Stripe, Conekta, Polar)
 * - Usage analytics
 * - Customer search and management
 */

'use client';

import { useState, useEffect } from 'react';

export interface AdminBillingDashboardProps {
  /**
   * Janua admin client instance
   */
  client: any;

  /**
   * Custom styling
   */
  className?: string;

  /**
   * Currency for display
   */
  currency?: 'USD' | 'MXN' | 'EUR';
}

interface BillingMetrics {
  mrr: number;
  arr: number;
  totalCustomers: number;
  activeSubscriptions: number;
  trialingSubscriptions: number;
  pastDueSubscriptions: number;
  canceledThisMonth: number;
  churnRate: number;
  revenueGrowth: number;
}

interface ProviderDistribution {
  stripe: number;
  conekta: number;
  polar: number;
}

interface RecentTransaction {
  id: string;
  customer_email: string;
  customer_name: string;
  amount: number;
  currency: string;
  provider: string;
  status: string;
  type: 'payment' | 'refund' | 'subscription';
  created_at: string;
}

interface SubscriptionsByPlan {
  plan_id: string;
  plan_name: string;
  count: number;
  mrr: number;
}

export function AdminBillingDashboard({
  client,
  className = '',
  currency = 'USD',
}: AdminBillingDashboardProps) {
  const [metrics, setMetrics] = useState<BillingMetrics | null>(null);
  const [providerDistribution, setProviderDistribution] = useState<ProviderDistribution | null>(null);
  const [recentTransactions, setRecentTransactions] = useState<RecentTransaction[]>([]);
  const [subscriptionsByPlan, setSubscriptionsByPlan] = useState<SubscriptionsByPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | '1y'>('30d');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadDashboardData();
  }, [client, dateRange]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load all dashboard data in parallel
      const [metricsData, providerData, transactionsData, plansData] = await Promise.all([
        client.admin.billing.getMetrics({ range: dateRange }),
        client.admin.billing.getProviderDistribution(),
        client.admin.billing.getRecentTransactions({ limit: 10 }),
        client.admin.billing.getSubscriptionsByPlan(),
      ]);

      setMetrics(metricsData);
      setProviderDistribution(providerData);
      setRecentTransactions(transactionsData);
      setSubscriptionsByPlan(plansData);
    } catch (err: any) {
      setError(err.message || 'Failed to load billing dashboard');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number, curr: string = currency) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: curr,
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      succeeded: 'text-green-600 bg-green-100',
      pending: 'text-yellow-600 bg-yellow-100',
      failed: 'text-red-600 bg-red-100',
      refunded: 'text-gray-600 bg-gray-100',
    };
    return colors[status] || 'text-gray-600 bg-gray-100';
  };

  const getProviderColor = (provider: string) => {
    const colors: Record<string, string> = {
      stripe: 'bg-indigo-500',
      conekta: 'bg-purple-500',
      polar: 'bg-blue-500',
    };
    return colors[provider] || 'bg-gray-500';
  };

  if (loading) {
    return (
      <div className={`flex items-center justify-center p-12 ${className}`}>
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`rounded-lg bg-red-50 p-6 ${className}`}>
        <h3 className="text-lg font-medium text-red-800">Error Loading Dashboard</h3>
        <p className="mt-2 text-sm text-red-700">{error}</p>
        <button
          onClick={loadDashboardData}
          className="mt-4 px-4 py-2 text-sm font-medium text-red-600 bg-white border border-red-600 rounded-md hover:bg-red-50"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Billing Dashboard</h1>
          <p className="mt-1 text-sm text-gray-600">
            Monitor revenue, subscriptions, and payment providers
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Date Range Selector */}
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value as any)}
            className="px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="1y">Last year</option>
          </select>
          <button
            onClick={loadDashboardData}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Metrics Cards */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* MRR Card */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-600">Monthly Recurring Revenue</h3>
              <span className="text-2xl">💰</span>
            </div>
            <p className="mt-2 text-3xl font-bold text-gray-900">
              {formatCurrency(metrics.mrr)}
            </p>
            <p className={`mt-1 text-sm ${metrics.revenueGrowth >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {metrics.revenueGrowth >= 0 ? '↑' : '↓'} {Math.abs(metrics.revenueGrowth)}% vs last period
            </p>
          </div>

          {/* ARR Card */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-600">Annual Recurring Revenue</h3>
              <span className="text-2xl">📈</span>
            </div>
            <p className="mt-2 text-3xl font-bold text-gray-900">
              {formatCurrency(metrics.arr)}
            </p>
            <p className="mt-1 text-sm text-gray-500">
              {metrics.totalCustomers} total customers
            </p>
          </div>

          {/* Active Subscriptions Card */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-600">Active Subscriptions</h3>
              <span className="text-2xl">📋</span>
            </div>
            <p className="mt-2 text-3xl font-bold text-gray-900">
              {metrics.activeSubscriptions}
            </p>
            <div className="mt-1 flex items-center gap-2 text-sm">
              <span className="text-blue-600">{metrics.trialingSubscriptions} trialing</span>
              <span className="text-gray-400">•</span>
              <span className="text-yellow-600">{metrics.pastDueSubscriptions} past due</span>
            </div>
          </div>

          {/* Churn Rate Card */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-600">Churn Rate</h3>
              <span className="text-2xl">📉</span>
            </div>
            <p className="mt-2 text-3xl font-bold text-gray-900">
              {metrics.churnRate.toFixed(1)}%
            </p>
            <p className="mt-1 text-sm text-gray-500">
              {metrics.canceledThisMonth} canceled this month
            </p>
          </div>
        </div>
      )}

      {/* Provider Distribution & Subscriptions by Plan */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Provider Distribution */}
        {providerDistribution && (
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Payment Provider Distribution</h3>
            <div className="space-y-4">
              {Object.entries(providerDistribution).map(([provider, count]) => {
                const total = Object.values(providerDistribution).reduce((a, b) => a + b, 0);
                const percentage = total > 0 ? (count / total) * 100 : 0;
                return (
                  <div key={provider} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium capitalize">{provider}</span>
                      <span className="text-gray-600">{count} ({percentage.toFixed(1)}%)</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${getProviderColor(provider)}`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Subscriptions by Plan */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Subscriptions by Plan</h3>
          {subscriptionsByPlan.length > 0 ? (
            <div className="space-y-3">
              {subscriptionsByPlan.map((plan) => (
                <div
                  key={plan.plan_id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div>
                    <p className="font-medium text-gray-900">{plan.plan_name}</p>
                    <p className="text-sm text-gray-600">{plan.count} subscribers</p>
                  </div>
                  <p className="font-semibold text-gray-900">
                    {formatCurrency(plan.mrr)}/mo
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No subscription data available</p>
          )}
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Recent Transactions</h3>
            <input
              type="text"
              placeholder="Search by email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Customer
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Amount
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Provider
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {recentTransactions
                .filter(
                  (tx) =>
                    !searchQuery ||
                    tx.customer_email.toLowerCase().includes(searchQuery.toLowerCase()) ||
                    tx.customer_name.toLowerCase().includes(searchQuery.toLowerCase())
                )
                .map((transaction) => (
                  <tr key={transaction.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {transaction.customer_name}
                        </p>
                        <p className="text-sm text-gray-500">{transaction.customer_email}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={transaction.type === 'refund' ? 'text-red-600' : 'text-gray-900'}>
                        {transaction.type === 'refund' ? '-' : ''}
                        {formatCurrency(transaction.amount, transaction.currency)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 capitalize">
                        {transaction.provider}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 capitalize">
                      {transaction.type}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(
                          transaction.status
                        )}`}
                      >
                        {transaction.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(transaction.created_at)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          {recentTransactions.length === 0 && (
            <div className="text-center py-8 text-sm text-gray-500">
              No transactions found
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
