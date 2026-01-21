'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Sidebar } from './sidebar'

interface DashboardLayoutProps {
  children: React.ReactNode
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter()
  const [user, setUser] = useState<{ name?: string; email?: string } | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const token = getCookie('janua_token')
        if (!token) {
          router.push('/login')
          return
        }

        const storedUser = localStorage.getItem('janua_user')
        if (storedUser) {
          setUser(JSON.parse(storedUser))
        }

        setIsLoading(false)
      } catch (error) {
        console.error('Failed to initialize auth:', error)
        router.push('/login')
      }
    }

    initializeAuth()
  }, [router])

  const getCookie = (name: string): string | null => {
    if (typeof document === 'undefined') return null
    const value = `; ${document.cookie}`
    const parts = value.split(`; ${name}=`)
    if (parts.length === 2) {
      return parts.pop()?.split(';').shift() || null
    }
    return null
  }

  const handleLogout = () => {
    document.cookie = 'janua_token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT'
    document.cookie = 'janua_token=; path=/; domain=.janua.dev; expires=Thu, 01 Jan 1970 00:00:01 GMT'
    localStorage.removeItem('janua_user')
    router.push('/login')
  }

  if (isLoading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="border-primary mx-auto mb-4 size-8 animate-spin rounded-full border-b-2"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-background flex h-screen overflow-hidden">
      <Sidebar user={user || undefined} onLogout={handleLogout} />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  )
}
