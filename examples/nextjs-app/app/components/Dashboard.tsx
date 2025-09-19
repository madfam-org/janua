'use client';

import { useSession, useOrganization } from '@plinto/react-sdk';

export function Dashboard() {
  const { session, sessions } = useSession();
  const { organization, organizations } = useOrganization();

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h2 className="text-lg font-medium text-gray-900 mb-4">Dashboard</h2>
      
      <div className="space-y-6">
        {/* Session Information */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Current Session</h3>
          <div className="bg-gray-50 rounded p-3">
            <dl className="text-sm">
              <dt className="inline font-medium text-gray-700">Session ID: </dt>
              <dd className="inline text-gray-900 font-mono">{session?.id?.substring(0, 8)}...</dd>
              <br />
              <dt className="inline font-medium text-gray-700">Created: </dt>
              <dd className="inline text-gray-900">
                {session?.createdAt && new Date(session.createdAt).toLocaleString()}
              </dd>
            </dl>
          </div>
        </div>

        {/* Active Sessions */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            Active Sessions ({sessions?.length || 0})
          </h3>
          <div className="space-y-2">
            {sessions?.slice(0, 3).map((s) => (
              <div key={s.id} className="flex items-center justify-between text-sm">
                <span className="text-gray-600">
                  {s.deviceInfo?.browser || 'Unknown'} • {s.ipAddress}
                </span>
                <span className="text-gray-500">
                  {new Date(s.lastActiveAt).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Organizations */}
        {organizations && organizations.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-2">Organizations</h3>
            <div className="space-y-2">
              {organizations.map((org) => (
                <div
                  key={org.id}
                  className={`border rounded p-3 ${
                    organization?.id === org.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}
                >
                  <div className="font-medium text-gray-900">{org.name}</div>
                  <div className="text-sm text-gray-500">{org.slug}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Features Demo */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Platform Features</h3>
          <div className="grid grid-cols-2 gap-2">
            {[
              'MFA Support',
              'Passkeys',
              'OAuth Providers',
              'Magic Links',
              'Webhooks',
              'Rate Limiting',
              'Audit Logs',
              'Team Management'
            ].map((feature) => (
              <div key={feature} className="flex items-center text-sm">
                <svg className="h-4 w-4 text-green-500 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span className="text-gray-700">{feature}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}