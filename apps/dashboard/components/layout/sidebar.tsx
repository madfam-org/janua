'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn, Button, Badge } from '@janua/ui'
import {
  Shield,
  BarChart3,
  Users,
  Key,
  Building2,
  Webhook,
  Settings,
  FileCheck,
  Lock,
  UserPlus,
  ChevronLeft,
  ChevronRight,
  LogOut,
  User,
  Activity,
  Globe,
  Code,
  Bell,
  UserCog,
  CreditCard,
  Mail,
  Server,
  Palette,
  Fingerprint,
  Monitor,
  ShieldCheck,
} from 'lucide-react'

interface NavItem {
  title: string
  href: string
  icon: React.ReactNode
  badge?: string
  badgeVariant?: 'default' | 'secondary' | 'destructive' | 'outline'
}

interface NavSection {
  title: string
  items: NavItem[]
}

const navSections: NavSection[] = [
  {
    title: 'Dashboard',
    items: [
      { title: 'Overview', href: '/', icon: <BarChart3 className="size-4" /> },
      { title: 'Users', href: '/users', icon: <Users className="size-4" /> },
      { title: 'Sessions', href: '/?tab=sessions', icon: <Monitor className="size-4" /> },
      { title: 'Organizations', href: '/organizations', icon: <Building2 className="size-4" /> },
    ],
  },
  {
    title: 'Authentication',
    items: [
      { title: 'SSO / SAML', href: '/settings/sso', icon: <Key className="size-4" />, badge: 'Enterprise', badgeVariant: 'secondary' },
      { title: 'MFA Settings', href: '/profile?tab=security', icon: <ShieldCheck className="size-4" /> },
      { title: 'Passkeys', href: '/profile?tab=security', icon: <Fingerprint className="size-4" /> },
      { title: 'OAuth Clients', href: '/settings/oauth-clients', icon: <Globe className="size-4" /> },
    ],
  },
  {
    title: 'Integrations',
    items: [
      { title: 'Webhooks', href: '/?tab=webhooks', icon: <Webhook className="size-4" /> },
      { title: 'API Keys', href: '/settings/api-keys', icon: <Code className="size-4" /> },
      { title: 'SCIM', href: '/settings/scim', icon: <Users className="size-4" />, badge: 'Enterprise', badgeVariant: 'secondary' },
    ],
  },
  {
    title: 'Security & Compliance',
    items: [
      { title: 'Audit Logs', href: '/audit-logs', icon: <Activity className="size-4" /> },
      { title: 'Security Alerts', href: '/settings/alerts', icon: <Bell className="size-4" /> },
      { title: 'Privacy', href: '/compliance', icon: <FileCheck className="size-4" /> },
    ],
  },
  {
    title: 'Settings',
    items: [
      { title: 'Invitations', href: '/settings/invitations', icon: <UserPlus className="size-4" /> },
      { title: 'Roles & Permissions', href: '/settings/roles', icon: <UserCog className="size-4" /> },
      { title: 'Policies', href: '/settings/policies', icon: <Lock className="size-4" /> },
      { title: 'Branding', href: '/settings/branding', icon: <Palette className="size-4" />, badge: 'Enterprise', badgeVariant: 'secondary' },
      { title: 'Billing', href: '/settings/billing', icon: <CreditCard className="size-4" /> },
      { title: 'Email Templates', href: '/settings/email-templates', icon: <Mail className="size-4" /> },
      { title: 'System', href: '/settings/system', icon: <Server className="size-4" />, badge: 'Admin', badgeVariant: 'outline' },
    ],
  },
]

interface SidebarProps {
  user?: {
    name?: string
    email?: string
  }
  onLogout?: () => void
}

export function Sidebar({ user, onLogout }: SidebarProps) {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/' && typeof window !== 'undefined' && !window.location.search.includes('tab=')
    if (href.startsWith('/') && !href.includes('?')) {
      if (href === '/users') return pathname.startsWith('/users')
      if (href === '/organizations') return pathname.startsWith('/organizations')
      if (href === '/audit-logs') return pathname.startsWith('/audit-logs')
      return pathname === href || pathname.startsWith(href + '/')
    }
    if (href.includes('?tab=')) {
      const tab = href.split('?tab=')[1]
      return pathname === '/' && typeof window !== 'undefined' && window.location.search.includes(`tab=${tab}`)
    }
    if (href.includes('?')) {
      return pathname === href.split('?')[0]
    }
    return pathname.startsWith(href)
  }

  return (
    <div
      className={cn(
        'bg-card flex h-screen flex-col border-r transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b p-4">
        {!collapsed && (
          <div className="flex items-center space-x-2">
            <Shield className="text-primary size-6" />
            <span className="font-semibold">Janua</span>
          </div>
        )}
        {collapsed && <Shield className="text-primary mx-auto size-6" />}
        <Button
          variant="ghost"
          size="icon"
          className={cn('size-8', collapsed && 'mx-auto')}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? (
            <ChevronRight className="size-4" />
          ) : (
            <ChevronLeft className="size-4" />
          )}
        </Button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-2">
        {navSections.map((section) => (
          <div key={section.title} className="mb-4">
            {!collapsed && (
              <h3 className="text-muted-foreground px-3 py-2 text-xs font-semibold uppercase tracking-wider">
                {section.title}
              </h3>
            )}
            <ul className="space-y-1">
              {section.items.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                      isActive(item.href)
                        ? 'bg-primary/10 text-primary font-medium'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      collapsed && 'justify-center px-2'
                    )}
                    title={collapsed ? item.title : undefined}
                  >
                    {item.icon}
                    {!collapsed && (
                      <>
                        <span className="flex-1">{item.title}</span>
                        {item.badge && (
                          <Badge variant={item.badgeVariant} className="text-xs">
                            {item.badge}
                          </Badge>
                        )}
                      </>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t p-2">
        <Link
          href="/settings"
          className={cn(
            'text-muted-foreground hover:bg-muted hover:text-foreground flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
            isActive('/settings') && pathname === '/settings' && 'bg-primary/10 text-primary font-medium',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? 'All Settings' : undefined}
        >
          <Settings className="size-4" />
          {!collapsed && <span>All Settings</span>}
        </Link>
        <Link
          href="/profile"
          className={cn(
            'text-muted-foreground hover:bg-muted hover:text-foreground flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? 'Profile' : undefined}
        >
          <User className="size-4" />
          {!collapsed && (
            <div className="flex-1 truncate">
              <span className="block truncate">{user?.name || user?.email || 'Profile'}</span>
            </div>
          )}
        </Link>
        {onLogout && (
          <button
            onClick={onLogout}
            className={cn(
              'text-muted-foreground hover:bg-destructive/10 hover:text-destructive flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
              collapsed && 'justify-center px-2'
            )}
            title={collapsed ? 'Sign out' : undefined}
          >
            <LogOut className="size-4" />
            {!collapsed && <span>Sign out</span>}
          </button>
        )}
      </div>
    </div>
  )
}
