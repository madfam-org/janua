import { Shield, CreditCard, Server, Mail } from 'lucide-react'
import type { SecretCategory } from './types'

export const CATEGORY_ICONS: Record<SecretCategory, React.ReactNode> = {
  authentication: <Shield className="size-4" />,
  payment: <CreditCard className="size-4" />,
  infrastructure: <Server className="size-4" />,
  email: <Mail className="size-4" />,
}

export const CATEGORY_LABELS: Record<SecretCategory, string> = {
  authentication: 'Authentication',
  payment: 'Payment',
  infrastructure: 'Infrastructure',
  email: 'Email',
}
