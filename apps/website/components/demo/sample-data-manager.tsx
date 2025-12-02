'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Users, RefreshCw, Database, Plus } from 'lucide-react'
import { useDemoFeatures } from '@/hooks/useEnvironment'

export function SampleDataManager() {
  const [loading, setLoading] = useState(false)
  const [sampleUsers, setSampleUsers] = useState<any[]>([])
  const { isDemo, generateSampleUsers } = useDemoFeatures()

  if (!isDemo) {
    return null
  }

  const loadSampleUsers = () => {
    setLoading(true)
    setTimeout(() => {
      const users = generateSampleUsers()
      setSampleUsers(users)
      setLoading(false)
    }, 800)
  }

  const addRandomUser = () => {
    const randomNames = [
      { name: 'David Engineer', email: 'david@demo.com', role: 'admin' },
      { name: 'Eva Manager', email: 'eva@demo.com', role: 'member' },
      { name: 'Frank Developer', email: 'frank@demo.com', role: 'viewer' },
      { name: 'Grace Analyst', email: 'grace@demo.com', role: 'member' },
    ]
    
    const randomUser = randomNames[Math.floor(Math.random() * randomNames.length)]
    setSampleUsers(prev => [...prev, { 
      ...randomUser, 
      id: Math.random().toString(36).substr(2, 9) 
    }])
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="h-5 w-5 text-green-600" />
          Sample Data Manager
        </CardTitle>
        <CardDescription>
          Generate and manage sample users for demonstration
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Button 
            onClick={loadSampleUsers}
            disabled={loading}
            variant="outline"
            className="flex-1"
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Loading...
              </>
            ) : (
              <>
                <Users className="h-4 w-4 mr-2" />
                Generate Users
              </>
            )}
          </Button>
          <Button 
            onClick={addRandomUser}
            disabled={sampleUsers.length === 0}
            variant="outline"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        {sampleUsers.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-2"
          >
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              Sample Users ({sampleUsers.length})
            </h4>
            {sampleUsers.map((user, index) => (
              <motion.div
                key={user.id || index}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
              >
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-900 dark:text-white">
                    {user.name}
                  </div>
                  <div className="text-xs text-gray-500">
                    {user.email}
                  </div>
                </div>
                <span className={`px-2 py-1 text-xs rounded-full ${
                  user.role === 'admin' 
                    ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                    : user.role === 'member'
                    ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                    : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                }`}>
                  {user.role}
                </span>
              </motion.div>
            ))}
          </motion.div>
        )}

        <div className="pt-3 border-t border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500">
            <strong>Demo Feature:</strong> Generated users are for demonstration only and are not persisted. 
            In production, user data is securely stored and managed.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}