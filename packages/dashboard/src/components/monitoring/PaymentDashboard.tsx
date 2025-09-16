import React, { useState, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line, Bar, Doughnut } from 'react-chartjs-2';
import { formatDistanceToNow } from 'date-fns';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface DashboardMetrics {
  overview: {
    totalPayments: number;
    totalRevenue: number;
    successRate: number;
    activeCustomers: number;
  };
  providers: {
    name: string;
    health: {
      status: 'healthy' | 'degraded' | 'unhealthy';
      uptime: number;
      errorRate: number;
      latency: { p50: number; p95: number; p99: number };
    };
    volume: number;
    revenue: number;
    successRate: number;
  }[];
  trends: {
    payments: { timestamp: number; value: number }[];
    revenue: { timestamp: number; value: number }[];
    successRate: { timestamp: number; value: number }[];
  };
  alerts: {
    id: string;
    severity: 'info' | 'warning' | 'critical';
    title: string;
    description: string;
    timestamp: Date;
    acknowledged: boolean;
  }[];
}

export const PaymentDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>('all');
  const [timeRange, setTimeRange] = useState<'1h' | '24h' | '7d' | '30d'>('24h');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    fetchDashboardMetrics();

    if (autoRefresh) {
      const interval = setInterval(fetchDashboardMetrics, 10000); // Refresh every 10 seconds
      return () => clearInterval(interval);
    }
  }, [timeRange, autoRefresh]);

  const fetchDashboardMetrics = async () => {
    try {
      const response = await fetch(`/api/monitoring/dashboard?timeRange=${timeRange}`);
      if (!response.ok) throw new Error('Failed to fetch metrics');
      const data = await response.json();
      setMetrics(data);
      setLoading(false);
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  };

  const acknowledgeAlert = async (alertId: string) => {
    try {
      await fetch(`/api/monitoring/alerts/${alertId}/acknowledge`, { method: 'POST' });
      fetchDashboardMetrics();
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-red-600">Error: {error || 'No metrics available'}</div>
      </div>
    );
  }

  // Chart configurations
  const paymentTrendChart = {
    labels: metrics.trends.payments.map(p =>
      new Date(p.timestamp).toLocaleTimeString()
    ),
    datasets: [
      {
        label: 'Payments',
        data: metrics.trends.payments.map(p => p.value),
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true
      }
    ]
  };

  const revenueTrendChart = {
    labels: metrics.trends.revenue.map(p =>
      new Date(p.timestamp).toLocaleTimeString()
    ),
    datasets: [
      {
        label: 'Revenue',
        data: metrics.trends.revenue.map(p => p.value),
        borderColor: 'rgb(16, 185, 129)',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        fill: true
      }
    ]
  };

  const successRateTrendChart = {
    labels: metrics.trends.successRate.map(p =>
      new Date(p.timestamp).toLocaleTimeString()
    ),
    datasets: [
      {
        label: 'Success Rate (%)',
        data: metrics.trends.successRate.map(p => p.value),
        borderColor: 'rgb(251, 146, 60)',
        backgroundColor: 'rgba(251, 146, 60, 0.1)',
        fill: true
      }
    ]
  };

  const providerDistributionChart = {
    labels: metrics.providers.map(p => p.name),
    datasets: [
      {
        label: 'Transaction Volume',
        data: metrics.providers.map(p => p.volume),
        backgroundColor: [
          'rgba(239, 68, 68, 0.8)',
          'rgba(59, 130, 246, 0.8)',
          'rgba(16, 185, 129, 0.8)'
        ]
      }
    ]
  };

  const providerRevenueChart = {
    labels: metrics.providers.map(p => p.name),
    datasets: [
      {
        label: 'Revenue',
        data: metrics.providers.map(p => p.revenue),
        backgroundColor: 'rgba(99, 102, 241, 0.8)'
      }
    ]
  };

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Payment Monitoring Dashboard</h1>
        <div className="mt-4 flex items-center justify-between">
          <div className="flex gap-2">
            {(['1h', '24h', '7d', '30d'] as const).map(range => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`px-4 py-2 rounded ${
                  timeRange === range
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-100'
                }`}
              >
                {range}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="mr-2"
              />
              Auto-refresh
            </label>
            <span className="text-sm text-gray-500">
              Last updated: {new Date().toLocaleTimeString()}
            </span>
          </div>
        </div>
      </div>

      {/* Alerts */}
      {metrics.alerts.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-3">Active Alerts</h2>
          <div className="space-y-2">
            {metrics.alerts.map(alert => (
              <div
                key={alert.id}
                className={`p-4 rounded-lg flex items-center justify-between ${
                  alert.severity === 'critical'
                    ? 'bg-red-100 border-l-4 border-red-500'
                    : alert.severity === 'warning'
                    ? 'bg-yellow-100 border-l-4 border-yellow-500'
                    : 'bg-blue-100 border-l-4 border-blue-500'
                }`}
              >
                <div>
                  <div className="font-semibold">{alert.title}</div>
                  <div className="text-sm text-gray-600">{alert.description}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })}
                  </div>
                </div>
                {!alert.acknowledged && (
                  <button
                    onClick={() => acknowledgeAlert(alert.id)}
                    className="px-3 py-1 bg-white rounded text-sm hover:bg-gray-100"
                  >
                    Acknowledge
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm text-gray-500">Total Payments</div>
          <div className="text-3xl font-bold text-gray-900">
            {metrics.overview.totalPayments.toLocaleString()}
          </div>
          <div className="mt-2 text-sm text-green-600">
            +12% from previous period
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm text-gray-500">Total Revenue</div>
          <div className="text-3xl font-bold text-gray-900">
            ${metrics.overview.totalRevenue.toLocaleString()}
          </div>
          <div className="mt-2 text-sm text-green-600">
            +8% from previous period
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm text-gray-500">Success Rate</div>
          <div className="text-3xl font-bold text-gray-900">
            {metrics.overview.successRate.toFixed(1)}%
          </div>
          <div className="mt-2 text-sm text-gray-500">
            Industry avg: 94%
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm text-gray-500">Active Customers</div>
          <div className="text-3xl font-bold text-gray-900">
            {metrics.overview.activeCustomers.toLocaleString()}
          </div>
          <div className="mt-2 text-sm text-green-600">
            +5% from previous period
          </div>
        </div>
      </div>

      {/* Provider Health */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold mb-3">Provider Health</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {metrics.providers.map(provider => (
            <div key={provider.name} className="bg-white p-4 rounded-lg shadow">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold capitalize">{provider.name}</h3>
                <span
                  className={`px-2 py-1 rounded text-xs font-semibold ${
                    provider.health.status === 'healthy'
                      ? 'bg-green-100 text-green-800'
                      : provider.health.status === 'degraded'
                      ? 'bg-yellow-100 text-yellow-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {provider.health.status}
                </span>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Uptime</span>
                  <span className="font-medium">{provider.health.uptime.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Error Rate</span>
                  <span className="font-medium">{provider.health.errorRate.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Latency (p95)</span>
                  <span className="font-medium">{provider.health.latency.p95}ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Success Rate</span>
                  <span className="font-medium">{provider.successRate.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Volume</span>
                  <span className="font-medium">{provider.volume.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Revenue</span>
                  <span className="font-medium">${provider.revenue.toLocaleString()}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-4">Payment Trend</h3>
          <Line
            data={paymentTrendChart}
            options={{
              responsive: true,
              plugins: {
                legend: { display: false },
                tooltip: {
                  mode: 'index',
                  intersect: false
                }
              },
              scales: {
                y: {
                  beginAtZero: true
                }
              }
            }}
          />
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-4">Revenue Trend</h3>
          <Line
            data={revenueTrendChart}
            options={{
              responsive: true,
              plugins: {
                legend: { display: false },
                tooltip: {
                  mode: 'index',
                  intersect: false,
                  callbacks: {
                    label: (context) => `$${context.parsed.y.toLocaleString()}`
                  }
                }
              },
              scales: {
                y: {
                  beginAtZero: true
                }
              }
            }}
          />
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-4">Success Rate Trend</h3>
          <Line
            data={successRateTrendChart}
            options={{
              responsive: true,
              plugins: {
                legend: { display: false },
                tooltip: {
                  mode: 'index',
                  intersect: false,
                  callbacks: {
                    label: (context) => `${context.parsed.y.toFixed(1)}%`
                  }
                }
              },
              scales: {
                y: {
                  beginAtZero: true,
                  max: 100
                }
              }
            }}
          />
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-4">Provider Distribution</h3>
          <div className="h-64 flex items-center justify-center">
            <Doughnut
              data={providerDistributionChart}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    position: 'right'
                  }
                }
              }}
            />
          </div>
        </div>
      </div>

      {/* Provider Revenue Comparison */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">Provider Revenue Comparison</h3>
        <Bar
          data={providerRevenueChart}
          options={{
            responsive: true,
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: (context) => `$${context.parsed.y.toLocaleString()}`
                }
              }
            },
            scales: {
              y: {
                beginAtZero: true
              }
            }
          }}
        />
      </div>

      {/* Quick Actions */}
      <div className="mt-6 bg-white p-6 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
        <div className="flex gap-3">
          <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            Export Report
          </button>
          <button className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700">
            Configure Alerts
          </button>
          <button className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
            Run Health Check
          </button>
          <button className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700">
            View Audit Logs
          </button>
        </div>
      </div>
    </div>
  );
};