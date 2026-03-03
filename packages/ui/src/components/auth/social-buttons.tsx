import * as React from 'react'
import { Button } from '../button'
import { cn } from '../../lib/utils'
import { GoogleIcon, GitHubIcon, MicrosoftIcon, AppleIcon, JanuaIcon } from './social-icons'

export type SocialProvider = 'google' | 'github' | 'microsoft' | 'apple' | 'janua'

export interface SocialButtonProps {
  provider: SocialProvider
  onClick?: () => void
  disabled?: boolean
  className?: string
  /** Text override. Defaults to "Continue with {Provider}" */
  label?: string
  /** Animation delay index for stagger effect */
  animationIndex?: number
}

const providerConfig: Record<SocialProvider, {
  icon: React.ComponentType<{ className?: string }>
  label: string
  className: string
}> = {
  google: {
    icon: GoogleIcon,
    label: 'Continue with Google',
    className: 'bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 dark:bg-gray-800 dark:hover:bg-gray-700 dark:text-gray-200 dark:border-gray-600',
  },
  github: {
    icon: GitHubIcon,
    label: 'Continue with GitHub',
    className: 'bg-[#24292e] hover:bg-[#2f363d] text-white border-transparent',
  },
  microsoft: {
    icon: MicrosoftIcon,
    label: 'Continue with Microsoft',
    className: 'bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 dark:bg-gray-800 dark:hover:bg-gray-700 dark:text-gray-200 dark:border-gray-600',
  },
  apple: {
    icon: AppleIcon,
    label: 'Continue with Apple',
    className: 'bg-black hover:bg-gray-900 text-white border-transparent dark:bg-white dark:hover:bg-gray-100 dark:text-black',
  },
  janua: {
    icon: JanuaIcon,
    label: 'Sign in with Janua',
    className: 'bg-[hsl(221,83%,53%)] hover:bg-[hsl(221,83%,48%)] text-white border-transparent',
  },
}

export function SocialButton({
  provider,
  onClick,
  disabled,
  className,
  label,
  animationIndex = 0,
}: SocialButtonProps) {
  const config = providerConfig[provider]
  const Icon = config.icon

  return (
    <Button
      variant="outline"
      className={cn(
        'w-full relative justify-center gap-2 font-medium',
        config.className,
        className,
      )}
      onClick={onClick}
      disabled={disabled}
      style={{
        animation: `janua-fade-in 200ms ease ${animationIndex * 50}ms both`,
      }}
    >
      <Icon className="w-5 h-5 shrink-0" />
      {label || config.label}
    </Button>
  )
}

/** Convenience named exports */
export function GoogleButton(props: Omit<SocialButtonProps, 'provider'>) {
  return <SocialButton provider="google" {...props} />
}

export function GitHubButton(props: Omit<SocialButtonProps, 'provider'>) {
  return <SocialButton provider="github" {...props} />
}

export function MicrosoftButton(props: Omit<SocialButtonProps, 'provider'>) {
  return <SocialButton provider="microsoft" {...props} />
}

export function AppleButton(props: Omit<SocialButtonProps, 'provider'>) {
  return <SocialButton provider="apple" {...props} />
}

export function JanuaSSOButton(props: Omit<SocialButtonProps, 'provider'>) {
  return <SocialButton provider="janua" label="Sign in with Janua" {...props} />
}
