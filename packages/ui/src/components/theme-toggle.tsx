'use client'

import * as React from 'react'
import { Moon, Sun, Monitor } from 'lucide-react'
import { useTheme } from 'next-themes'

interface FloatingThemeToggleProps {
  className?: string
}

export function FloatingThemeToggle({ className = '' }: FloatingThemeToggleProps) {
  const [mounted, setMounted] = React.useState(false)
  const { theme, setTheme } = useTheme()

  React.useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return null
  }

  const cycleTheme = () => {
    if (theme === 'light') {
      setTheme('dark')
    } else if (theme === 'dark') {
      setTheme('system')
    } else {
      setTheme('light')
    }
  }

  const getIcon = () => {
    switch (theme) {
      case 'light':
        return <Sun className="h-4 w-4" />
      case 'dark':
        return <Moon className="h-4 w-4" />
      default:
        return <Monitor className="h-4 w-4" />
    }
  }

  const getLabel = () => {
    switch (theme) {
      case 'light':
        return 'Light'
      case 'dark':
        return 'Dark'
      default:
        return 'System'
    }
  }

  return (
    <button
      onClick={cycleTheme}
      className={`
        fixed bottom-4 right-4 z-50
        flex items-center gap-2 px-3 py-2
        bg-white dark:bg-gray-900
        border border-gray-200 dark:border-gray-800
        rounded-full shadow-lg
        text-sm text-gray-700 dark:text-gray-300
        hover:bg-gray-50 dark:hover:bg-gray-800
        transition-all duration-200
        ${className}
      `}
      aria-label={`Current theme: ${getLabel()}. Click to change.`}
    >
      {getIcon()}
      <span className="hidden sm:inline">{getLabel()}</span>
    </button>
  )
}

export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof import('next-themes').ThemeProvider>) {
  const { ThemeProvider: NextThemeProvider } = require('next-themes')
  return (
    <NextThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemeProvider>
  )
}
