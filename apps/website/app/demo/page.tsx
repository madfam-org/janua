import Link from 'next/link'
import {
  KeyRound,
  UserPlus,
  Shield,
  Smartphone,
  Building2,
  Users,
  FileCheck,
  UserCircle,
  Lock,
  Mail,
  Fingerprint,
  Key
} from 'lucide-react'

const demos = [
  {
    href: '/demo/signin',
    title: 'Sign In',
    description: 'Email/password, social login, magic links, and passkey authentication',
    icon: KeyRound,
    features: ['Email/Password', 'Google/GitHub OAuth', 'Passkeys', 'Magic Links'],
  },
  {
    href: '/demo/signup',
    title: 'Sign Up',
    description: 'User registration with email verification and password requirements',
    icon: UserPlus,
    features: ['Email Verification', 'Password Strength', 'Terms Acceptance', 'Custom Fields'],
  },
  {
    href: '/demo/mfa',
    title: 'Multi-Factor Auth',
    description: 'TOTP authenticator apps, SMS codes, and backup recovery codes',
    icon: Smartphone,
    features: ['TOTP Setup', 'SMS Verification', 'Backup Codes', 'Recovery Flow'],
  },
  {
    href: '/demo/security',
    title: 'Security Center',
    description: 'Session management, device tracking, and security alerts',
    icon: Shield,
    features: ['Active Sessions', 'Device Management', 'Login History', 'Security Alerts'],
  },
  {
    href: '/demo/sso',
    title: 'Enterprise SSO',
    description: 'SAML 2.0 and OIDC configuration for enterprise identity providers',
    icon: Key,
    features: ['SAML Setup', 'OIDC Config', 'IdP Testing', 'Attribute Mapping'],
  },
  {
    href: '/demo/organizations',
    title: 'Organizations',
    description: 'Multi-tenant workspaces with member management and invitations',
    icon: Building2,
    features: ['Create Orgs', 'Invite Members', 'Role Assignment', 'Org Switching'],
  },
  {
    href: '/demo/rbac',
    title: 'Roles & Permissions',
    description: 'Flexible RBAC with custom roles, permissions, and SCIM provisioning',
    icon: Users,
    features: ['Custom Roles', 'Fine-grained Permissions', 'SCIM Sync', 'Role Hierarchy'],
  },
  {
    href: '/demo/compliance',
    title: 'Compliance & Audit',
    description: 'Audit logging, GDPR tools, and compliance reporting',
    icon: FileCheck,
    features: ['Audit Logs', 'Data Export', 'Consent Management', 'Retention Policies'],
  },
  {
    href: '/demo/profile',
    title: 'User Profile',
    description: 'Profile management, email changes, and account settings',
    icon: UserCircle,
    features: ['Edit Profile', 'Change Email', 'Update Password', 'Delete Account'],
  },
]

export default function DemoHubPage() {
  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="text-center max-w-3xl mx-auto">
        <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-4">
          Experience Janua Authentication
        </h1>
        <p className="text-xl text-slate-600 dark:text-slate-400">
          Explore our production-ready authentication components.
          Every demo below is built with the same components you'll use in your app.
        </p>
      </div>

      {/* Demo Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {demos.map((demo) => {
          const Icon = demo.icon
          return (
            <Link
              key={demo.href}
              href={demo.href}
              className="group bg-white dark:bg-slate-800 rounded-xl shadow-sm hover:shadow-lg transition-all duration-200 p-6 border border-slate-200 dark:border-slate-700 hover:border-blue-500 dark:hover:border-blue-400"
            >
              <div className="flex items-start gap-4">
                <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg group-hover:bg-blue-500 transition-colors">
                  <Icon className="w-6 h-6 text-blue-600 dark:text-blue-400 group-hover:text-white transition-colors" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                    {demo.title}
                  </h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                    {demo.description}
                  </p>
                  <div className="flex flex-wrap gap-1 mt-3">
                    {demo.features.map((feature) => (
                      <span
                        key={feature}
                        className="text-xs px-2 py-1 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded"
                      >
                        {feature}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </Link>
          )
        })}
      </div>

      {/* Bottom CTA */}
      <div className="text-center pt-8">
        <p className="text-slate-600 dark:text-slate-400 mb-4">
          Like what you see? These exact components are available in your app.
        </p>
        <div className="flex justify-center gap-4">
          <Link
            href="https://app.janua.dev/signup"
            className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors"
          >
            Start Building Free
          </Link>
          <Link
            href="/pricing"
            className="px-6 py-3 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 font-semibold rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            View Pricing
          </Link>
        </div>
      </div>
    </div>
  )
}
