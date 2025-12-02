'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Zap, Globe, Server, ArrowUp, ArrowDown } from 'lucide-react'
import { useDemoFeatures } from '@/hooks/useEnvironment'

interface PerformanceMetric {
  name: string
  value: number
  unit: string
  icon: React.ReactNode
  description: string
}

export function PerformanceSimulator() {
  const [metrics, setMetrics] = useState<PerformanceMetric[]>([])
  const { performanceData, isDemo } = useDemoFeatures()

  useEffect(() => {
    if (!isDemo) return

    const baseMetrics: PerformanceMetric[] = [
      {
        name: 'Edge Verification',
        value: performanceData.edgeVerificationMs,
        unit: 'ms',
        icon: <Zap className="h-4 w-4" />,
        description: 'Token verification at edge locations'
      },
      {
        name: 'Auth Flow',
        value: performanceData.authFlowMs,
        unit: 'ms',
        icon: <Server className="h-4 w-4" />,
        description: 'Complete authentication process'
      },
      {
        name: 'Token Generation',
        value: performanceData.tokenGenerationMs,
        unit: 'ms',
        icon: <Globe className="h-4 w-4" />,
        description: 'JWT token creation and signing'
      },
      {
        name: 'Global Locations',
        value: performanceData.globalLocations,
        unit: 'regions',
        icon: <Globe className="h-4 w-4" />,
        description: 'Edge deployment locations'
      }
    ]

    setMetrics(baseMetrics)

    // Simulate real-time performance updates
    const interval = setInterval(() => {
      setMetrics(prevMetrics =>
        prevMetrics.map(metric => ({
          ...metric,
          value: metric.unit === 'ms' 
            ? Math.max(1, metric.value + (Math.random() - 0.5) * 10)
            : metric.value
        }))
      )
    }, 3000)

    return () => clearInterval(interval)
  }, [isDemo, performanceData])

  if (!isDemo) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-blue-600" />
          Performance Monitor
        </CardTitle>
        <CardDescription>
          Real-time performance metrics from global edge locations
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {metrics.map((metric, index) => (
            <motion.div
              key={metric.name}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.1 }}
              className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-950/30 dark:to-purple-950/30"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {metric.icon}
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {metric.name}
                  </span>
                </div>
                {metric.unit === 'ms' && (
                  <div className="text-green-600 dark:text-green-400">
                    <ArrowUp className="h-3 w-3" />
                  </div>
                )}
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {Math.round(metric.value)}
                <span className="text-sm font-normal text-gray-500 ml-1">
                  {metric.unit}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {metric.description}
              </p>
            </motion.div>
          ))}
        </div>
        <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
          <p className="text-xs text-amber-700 dark:text-amber-300">
            <strong>Demo Note:</strong> These metrics are simulated for demonstration purposes. 
            Production performance may vary based on your specific configuration and usage patterns.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}