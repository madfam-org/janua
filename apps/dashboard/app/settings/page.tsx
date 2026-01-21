'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Badge } from '@janua/ui'
import Link from 'next/link'
import {
  Settings,
  Shield,
  Users,
  Key,
  UserPlus,
  FileCheck,
  Lock,
  ChevronRight,
  ArrowLeft,
} from 'lucide-react'

interface SettingsSection {
  title: string
  description: string
  href: string
  icon: React.ReactNode
  badge?: string
  badgeVariant?: 'default' | 'secondary' | 'destructive' | 'outline'
}

const settingsSections: SettingsSection[] = [
  {
    title: 'Single Sign-On (SSO)',
    description: 'Configure SAML 2.0 or OIDC identity providers for your organization',
    href: '/settings/sso',
    icon: <Key className="size-5" />,
    badge: 'Enterprise',
    badgeVariant: 'secondary',
  },
  {
    title: 'SCIM Provisioning',
    description: 'Automate user provisioning from your identity provider',
    href: '/settings/scim',
    icon: <Users className="size-5" />,
    badge: 'Enterprise',
    badgeVariant: 'secondary',
  },
  {
    title: 'Team Invitations',
    description: 'Invite team members and manage pending invitations',
    href: '/settings/invitations',
    icon: <UserPlus className="size-5" />,
  },
  {
    title: 'Security Settings',
    description: 'Configure password policies, MFA requirements, and session settings',
    href: '/profile',
    icon: <Shield className="size-5" />,
  },
]

const complianceSections: SettingsSection[] = [
  {
    title: 'Privacy & Compliance',
    description: 'Manage data privacy settings, consent, and data subject requests',
    href: '/compliance',
    icon: <FileCheck className="size-5" />,
  },
  {
    title: 'Audit Logs',
    description: 'View security events and user activity logs',
    href: '/audit-logs',
    icon: <Lock className="size-5" />,
    badge: 'Admin',
    badgeVariant: 'outline',
  },
]

function SettingsCard({ section }: { section: SettingsSection }) {
  return (
    <Link href={section.href}>
      <Card className="hover:border-primary/50 cursor-pointer transition-all hover:shadow-sm">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="bg-muted rounded-lg p-2">{section.icon}</div>
              <div>
                <CardTitle className="flex items-center gap-2 text-lg">
                  {section.title}
                  {section.badge && (
                    <Badge variant={section.badgeVariant}>{section.badge}</Badge>
                  )}
                </CardTitle>
              </div>
            </div>
            <ChevronRight className="text-muted-foreground size-5" />
          </div>
        </CardHeader>
        <CardContent>
          <CardDescription>{section.description}</CardDescription>
        </CardContent>
      </Card>
    </Link>
  )
}

export default function SettingsPage() {
  return (
    <div className="bg-background min-h-screen">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto p-4">
          <div className="flex items-center space-x-4">
            <Link href="/" className="text-muted-foreground hover:text-foreground">
              <ArrowLeft className="size-5" />
            </Link>
            <Settings className="text-primary size-8" />
            <div>
              <h1 className="text-2xl font-bold">Organization Settings</h1>
              <p className="text-muted-foreground text-sm">
                Configure authentication, security, and compliance settings
              </p>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto space-y-8 px-4 py-8">
        {/* Authentication & Access */}
        <div>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <Shield className="text-muted-foreground size-5" />
            Authentication & Access
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {settingsSections.map((section) => (
              <SettingsCard key={section.href} section={section} />
            ))}
          </div>
        </div>

        {/* Compliance & Audit */}
        <div>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <FileCheck className="text-muted-foreground size-5" />
            Compliance & Audit
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {complianceSections.map((section) => (
              <SettingsCard key={section.href} section={section} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
