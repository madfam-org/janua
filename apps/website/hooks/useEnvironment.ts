'use client'

import { useState, useEffect, useCallback } from 'react'

interface EnvironmentState {
  isDemo: boolean
  isDevelopment: boolean
  isProduction: boolean
  mounted: boolean
  showDemoNotice: () => boolean
}

export function useEnvironment(): EnvironmentState {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const isDemo = typeof window !== 'undefined' &&
    (window.location.pathname.startsWith('/demo') ||
     process.env.NEXT_PUBLIC_DEMO_MODE === 'true')

  const isDevelopment = process.env.NODE_ENV === 'development'
  const isProduction = process.env.NODE_ENV === 'production'

  const showDemoNotice = () => {
    if (typeof window === 'undefined') return false
    return window.location.pathname.startsWith('/demo')
  }

  return {
    isDemo,
    isDevelopment,
    isProduction,
    mounted,
    showDemoNotice,
  }
}

// Demo features hook for performance simulation and sample data
interface DemoFeaturesState {
  isDemo: boolean
  performanceData: {
    edgeVerificationMs: number
    tokenGenerationMs: number
    mfaVerificationMs: number
    sessionLookupMs: number
    authFlowMs: number
    globalLocations: number
  }
  sampleUsers: Array<{
    id: string
    email: string
    name: string
    role: string
  }>
  refreshSampleData: () => void
  generateSampleUsers: () => Array<{ id: string; name: string; email: string; role: string }>
}

export function useDemoFeatures(): DemoFeaturesState {
  const [performanceData, setPerformanceData] = useState({
    edgeVerificationMs: 12,
    tokenGenerationMs: 45,
    mfaVerificationMs: 23,
    sessionLookupMs: 8,
    authFlowMs: 85,
    globalLocations: 12,
  })

  const [sampleUsers] = useState([
    { id: '1', email: 'alice@example.com', name: 'Alice Johnson', role: 'admin' },
    { id: '2', email: 'bob@example.com', name: 'Bob Smith', role: 'user' },
    { id: '3', email: 'carol@example.com', name: 'Carol Williams', role: 'user' },
  ])

  const isDemo = typeof window !== 'undefined' &&
    (window.location.pathname.startsWith('/demo') ||
     process.env.NEXT_PUBLIC_DEMO_MODE === 'true')

  // Simulate realistic variance in performance metrics
  useEffect(() => {
    if (!isDemo) return

    const interval = setInterval(() => {
      setPerformanceData({
        edgeVerificationMs: 10 + Math.random() * 8,
        tokenGenerationMs: 40 + Math.random() * 15,
        mfaVerificationMs: 20 + Math.random() * 10,
        sessionLookupMs: 5 + Math.random() * 6,
        authFlowMs: 75 + Math.random() * 25,
        globalLocations: 12, // Static - doesn't change
      })
    }, 2000)

    return () => clearInterval(interval)
  }, [isDemo])

  const refreshSampleData = useCallback(() => {
    // Trigger a refresh of sample data
    setPerformanceData(prev => ({ ...prev }))
  }, [])

  const generateSampleUsers = useCallback(() => {
    return [
      { id: '1', name: 'Alice Admin', email: 'alice@demo.com', role: 'admin' },
      { id: '2', name: 'Bob Member', email: 'bob@demo.com', role: 'member' },
      { id: '3', name: 'Carol Viewer', email: 'carol@demo.com', role: 'viewer' },
    ]
  }, [])

  return {
    isDemo,
    performanceData,
    sampleUsers,
    refreshSampleData,
    generateSampleUsers,
  }
}

// Sample data manager hook
interface SampleDataState {
  users: Array<{
    id: string
    email: string
    name: string
    role: string
    createdAt: Date
    lastLogin: Date
  }>
  sessions: Array<{
    id: string
    userId: string
    device: string
    location: string
    createdAt: Date
  }>
  auditLogs: Array<{
    id: string
    action: string
    actor: string
    timestamp: Date
    details: string
  }>
  isLoading: boolean
  refresh: () => void
}

export function useSampleData(): SampleDataState {
  const [isLoading, setIsLoading] = useState(false)

  const users = [
    { id: '1', email: 'alice@example.com', name: 'Alice Johnson', role: 'admin', createdAt: new Date('2024-01-15'), lastLogin: new Date() },
    { id: '2', email: 'bob@example.com', name: 'Bob Smith', role: 'user', createdAt: new Date('2024-02-20'), lastLogin: new Date(Date.now() - 86400000) },
    { id: '3', email: 'carol@example.com', name: 'Carol Williams', role: 'user', createdAt: new Date('2024-03-10'), lastLogin: new Date(Date.now() - 172800000) },
  ]

  const sessions = [
    { id: 's1', userId: '1', device: 'Chrome on macOS', location: 'San Francisco, CA', createdAt: new Date() },
    { id: 's2', userId: '2', device: 'Safari on iOS', location: 'New York, NY', createdAt: new Date(Date.now() - 3600000) },
  ]

  const auditLogs = [
    { id: 'a1', action: 'login', actor: 'alice@example.com', timestamp: new Date(), details: 'Successful login via password' },
    { id: 'a2', action: 'mfa_enabled', actor: 'bob@example.com', timestamp: new Date(Date.now() - 7200000), details: 'Enabled TOTP MFA' },
    { id: 'a3', action: 'password_change', actor: 'carol@example.com', timestamp: new Date(Date.now() - 86400000), details: 'Password updated' },
  ]

  const refresh = useCallback(() => {
    setIsLoading(true)
    setTimeout(() => setIsLoading(false), 500)
  }, [])

  return {
    users,
    sessions,
    auditLogs,
    isLoading,
    refresh,
  }
}
