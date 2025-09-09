'use client'

import { useState } from 'react'
import { 
  Users, 
  Shield, 
  Key, 
  Activity,
  Settings,
  Bell,
  LogOut,
  Building2,
  CreditCard,
  BarChart3,
  Clock,
  AlertTriangle
} from 'lucide-react'
import { Button } from '@plinto/ui'

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('overview')

  const stats = [
    { label: 'Active Users', value: '142', change: '+12%', icon: Users, color: 'text-blue-600' },
    { label: 'API Calls (24h)', value: '48.2K', change: '+5%', icon: Activity, color: 'text-green-600' },
    { label: 'Sessions', value: '523', change: '+18%', icon: Shield, color: 'text-purple-600' },
    { label: 'Success Rate', value: '99.8%', change: '+0.2%', icon: BarChart3, color: 'text-orange-600' },
  ]

  const recentActivity = [
    { type: 'auth', message: 'New user registered', user: 'john.doe@example.com', time: '2 min ago' },
    { type: 'session', message: 'Session created', user: 'jane.smith@example.com', time: '5 min ago' },
    { type: 'api', message: 'API key rotated', user: 'admin@company.com', time: '15 min ago' },
    { type: 'security', message: 'Failed login attempt blocked', user: 'unknown', time: '1 hour ago' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-4">
              <div className="p-2 bg-brand-600 rounded-lg">
                <Shield className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Plinto Dashboard</h1>
                <p className="text-sm text-gray-500">Acme Corporation</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <button className="p-2 text-gray-400 hover:text-gray-500">
                <Bell className="h-5 w-5" />
              </button>
              <button className="p-2 text-gray-400 hover:text-gray-500">
                <Settings className="h-5 w-5" />
              </button>
              <div className="flex items-center space-x-2">
                <div className="text-sm text-right">
                  <div className="font-medium text-gray-900">John Doe</div>
                  <div className="text-gray-500">Admin</div>
                </div>
                <button className="p-2 text-gray-400 hover:text-gray-500">
                  <LogOut className="h-5 w-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Navigation Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {['overview', 'users', 'sessions', 'api-keys', 'organization', 'billing'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-2 px-1 border-b-2 font-medium text-sm capitalize ${
                  activeTab === tab
                    ? 'border-brand-500 text-brand-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.replace('-', ' ')}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="mt-8">
          {activeTab === 'overview' && (
            <div className="space-y-8">
              {/* Stats Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {stats.map((stat) => {
                  const Icon = stat.icon
                  return (
                    <div key={stat.label} className="bg-white p-6 rounded-lg shadow">
                      <div className="flex items-center justify-between mb-4">
                        <Icon className={`h-8 w-8 ${stat.color}`} />
                        <span className={`text-sm font-medium ${
                          stat.change.startsWith('+') ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {stat.change}
                        </span>
                      </div>
                      <div className="text-2xl font-bold text-gray-900">{stat.value}</div>
                      <div className="text-sm text-gray-500">{stat.label}</div>
                    </div>
                  )
                })}
              </div>

              {/* Recent Activity */}
              <div className="bg-white rounded-lg shadow">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900">Recent Activity</h3>
                </div>
                <div className="px-6 py-4">
                  <div className="space-y-4">
                    {recentActivity.map((activity, index) => (
                      <div key={index} className="flex items-start space-x-3">
                        <div className={`p-2 rounded-full ${
                          activity.type === 'auth' ? 'bg-blue-100' :
                          activity.type === 'session' ? 'bg-green-100' :
                          activity.type === 'api' ? 'bg-purple-100' :
                          'bg-red-100'
                        }`}>
                          {activity.type === 'auth' && <Users className="h-4 w-4 text-blue-600" />}
                          {activity.type === 'session' && <Shield className="h-4 w-4 text-green-600" />}
                          {activity.type === 'api' && <Key className="h-4 w-4 text-purple-600" />}
                          {activity.type === 'security' && <AlertTriangle className="h-4 w-4 text-red-600" />}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-sm font-medium text-gray-900">{activity.message}</p>
                              <p className="text-sm text-gray-500">{activity.user}</p>
                            </div>
                            <span className="text-xs text-gray-400">{activity.time}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Button className="w-full justify-start">
                    <Users className="h-4 w-4 mr-2" />
                    Invite User
                  </Button>
                  <Button variant="outline" className="w-full justify-start">
                    <Key className="h-4 w-4 mr-2" />
                    Create API Key
                  </Button>
                  <Button variant="outline" className="w-full justify-start">
                    <Shield className="h-4 w-4 mr-2" />
                    Security Settings
                  </Button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'users' && <UsersTab />}
          {activeTab === 'sessions' && <SessionsTab />}
          {activeTab === 'api-keys' && <ApiKeysTab />}
          {activeTab === 'organization' && <OrganizationTab />}
          {activeTab === 'billing' && <BillingTab />}
        </div>
      </div>
    </div>
  )
}

function UsersTab() {
  const users = [
    { id: '1', name: 'John Doe', email: 'john.doe@example.com', role: 'Admin', status: 'active', lastActive: '2 min ago' },
    { id: '2', name: 'Jane Smith', email: 'jane.smith@example.com', role: 'Member', status: 'active', lastActive: '1 hour ago' },
    { id: '3', name: 'Bob Johnson', email: 'bob.johnson@example.com', role: 'Member', status: 'inactive', lastActive: '3 days ago' },
  ]

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">Users</h3>
        <Button size="sm">
          <Users className="h-4 w-4 mr-2" />
          Invite User
        </Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Active</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-b border-gray-200 hover:bg-gray-50">
                <td className="px-6 py-4">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{user.name}</div>
                    <div className="text-sm text-gray-500">{user.email}</div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800">
                    {user.role}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                    user.status === 'active' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-gray-100 text-gray-800'
                  }`}>
                    {user.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">{user.lastActive}</td>
                <td className="px-6 py-4">
                  <button className="text-sm text-brand-600 hover:text-brand-800">Manage</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SessionsTab() {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Active Sessions</h3>
      <p className="text-gray-600">Session management features coming soon...</p>
    </div>
  )
}

function ApiKeysTab() {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">API Keys</h3>
      <p className="text-gray-600">API key management features coming soon...</p>
    </div>
  )
}

function OrganizationTab() {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Organization Settings</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Organization Name</label>
            <input 
              type="text" 
              defaultValue="Acme Corporation"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-brand-500 focus:border-brand-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Organization ID</label>
            <input 
              type="text" 
              value="org_1234567890"
              disabled
              className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500"
            />
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Security Settings</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-medium text-gray-900">Two-Factor Authentication</h4>
              <p className="text-sm text-gray-500">Require 2FA for all users</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
            </label>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-medium text-gray-900">Session Timeout</h4>
              <p className="text-sm text-gray-500">Automatically sign out inactive users</p>
            </div>
            <select className="px-3 py-1 border border-gray-300 rounded-md text-sm">
              <option>15 minutes</option>
              <option>30 minutes</option>
              <option>1 hour</option>
              <option>24 hours</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}

function BillingTab() {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Current Plan</h3>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h4 className="text-xl font-bold text-gray-900">Pro Plan</h4>
            <p className="text-gray-500">$69/month • Up to 10,000 MAU</p>
          </div>
          <Button>Upgrade Plan</Button>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Monthly Active Users</span>
            <span className="font-medium">142 / 10,000</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">API Calls (this month)</span>
            <span className="font-medium">1.4M / Unlimited</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Next billing date</span>
            <span className="font-medium">Feb 1, 2024</span>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Payment Method</h3>
        <div className="flex items-center space-x-4">
          <CreditCard className="h-8 w-8 text-gray-400" />
          <div>
            <p className="text-sm font-medium text-gray-900">•••• •••• •••• 4242</p>
            <p className="text-sm text-gray-500">Expires 12/25</p>
          </div>
        </div>
      </div>
    </div>
  )
}