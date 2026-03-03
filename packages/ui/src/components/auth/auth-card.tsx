import * as React from 'react'
import { Card } from '../card'
import { cn } from '../../lib/utils'

export type AuthCardLayout = 'card' | 'modal' | 'page'

export interface AuthCardProps {
  children: React.ReactNode
  className?: string
  layout?: AuthCardLayout
  /** Logo element or URL */
  logo?: React.ReactNode | string
  /** Header content (above main content) */
  header?: React.ReactNode
  /** Footer content (below main content) */
  footer?: React.ReactNode
}

export function AuthCard({
  children,
  className,
  layout = 'card',
  logo,
  header,
  footer,
}: AuthCardProps) {
  const logoElement = typeof logo === 'string'
    ? <img src={logo} alt="Logo" className="h-12" />
    : logo

  const card = (
    <Card
      className={cn(
        'w-full max-w-md mx-auto p-6',
        'transition-all duration-[var(--janua-transition-base)]',
        layout === 'modal' && 'shadow-lg',
        layout === 'page' && 'border-0 shadow-none bg-transparent',
        className,
      )}
      style={{
        borderRadius: 'var(--janua-radius-card)',
        boxShadow: layout === 'card' ? 'var(--janua-shadow-card)' : undefined,
      }}
    >
      {logoElement && (
        <div className="flex justify-center mb-6" style={{ animation: 'janua-fade-in 300ms ease' }}>
          {logoElement}
        </div>
      )}
      {header}
      {children}
      {footer}
    </Card>
  )

  if (layout === 'modal') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" style={{ animation: 'janua-fade-in 200ms ease' }}>
        <div style={{ animation: 'janua-slide-up 300ms ease' }}>
          {card}
        </div>
      </div>
    )
  }

  if (layout === 'page') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        {card}
      </div>
    )
  }

  return card
}
