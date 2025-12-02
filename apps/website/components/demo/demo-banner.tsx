'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@janua/ui'
import { X, Info, ExternalLink } from 'lucide-react'
import { useEnvironment } from '@/hooks/useEnvironment'

export function DemoBanner() {
  const [dismissed, setDismissed] = useState(false)
  const { isDemo, showDemoNotice, mounted } = useEnvironment()

  if (!mounted || !isDemo || !showDemoNotice?.() || dismissed) {
    return null
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -50 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -50 }}
        className="bg-gradient-to-r from-blue-600 to-purple-600 text-white"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between py-3">
            <div className="flex items-center space-x-3">
              <Info className="h-5 w-5 flex-shrink-0" />
              <div className="text-sm">
                <span className="font-medium">Demo Environment</span>
                <span className="ml-2">
                  Experience Janua's authentication platform with simulated data and performance.
                </span>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => window.open('https://janua.dev/contact', '_blank')}
                className="text-white hover:bg-white/20 text-xs"
              >
                Try Production
                <ExternalLink className="ml-1 h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setDismissed(true)}
                className="text-white hover:bg-white/20 p-1"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}