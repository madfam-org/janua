'use client';

import { useAuth } from '@plinto/react-sdk';
import { LoginForm } from './components/LoginForm';
import { UserProfile } from './components/UserProfile';
import { Dashboard } from './components/Dashboard';

export default function Home() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Plinto Authentication Example
          </h1>
          <p className="text-lg text-gray-600">
            Production-ready authentication with Plinto SDK
          </p>
        </div>

        {!isAuthenticated ? (
          <div className="max-w-md mx-auto">
            <LoginForm />
          </div>
        ) : (
          <div className="space-y-8">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <p className="text-green-800">
                ✓ Authenticated as <strong>{user?.email}</strong>
              </p>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <UserProfile />
              <Dashboard />
            </div>
          </div>
        )}
      </div>
    </main>
  );
}