'use client';

import { useAuth, useUser } from '@plinto/react-sdk';

export function UserProfile() {
  const { signOut } = useAuth();
  const { user, updateProfile } = useUser();

  if (!user) return null;

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h2 className="text-lg font-medium text-gray-900 mb-4">User Profile</h2>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Email</label>
          <p className="mt-1 text-sm text-gray-900">{user.email}</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">User ID</label>
          <p className="mt-1 text-sm text-gray-900 font-mono">{user.id}</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Created</label>
          <p className="mt-1 text-sm text-gray-900">
            {new Date(user.createdAt).toLocaleDateString()}
          </p>
        </div>

        {user.emailVerified && (
          <div className="flex items-center">
            <svg className="h-5 w-5 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="text-sm text-green-600">Email verified</span>
          </div>
        )}

        <div className="pt-4 border-t">
          <button
            onClick={() => signOut()}
            className="w-full inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}