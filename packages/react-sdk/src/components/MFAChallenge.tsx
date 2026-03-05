import React from 'react'
import { MFAChallenge as UIMFAChallenge } from '@janua/ui/components/auth'
import { useJanua } from '../provider'

export interface MFAChallengeProps {
  /** Optional custom class name */
  className?: string
  /** Callback when code is verified */
  onVerify?: (code: string) => Promise<void>
  /** Callback to use backup code instead */
  onUseBackupCode?: () => void
  /** Callback to request new code (SMS) */
  onRequestNewCode?: () => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
  /** MFA method type */
  method?: 'totp' | 'sms'
  /** Show use backup code option */
  showBackupCodeOption?: boolean
  /** Allow resending code (for SMS) */
  allowResend?: boolean
}

/**
 * MFAChallenge component - thin wrapper around @janua/ui MFAChallenge
 *
 * Injects user email from Janua context for display.
 */
export function MFAChallenge({
  className,
  onVerify,
  onUseBackupCode,
  onRequestNewCode,
  onError,
  method,
  showBackupCodeOption,
  allowResend,
}: MFAChallengeProps) {
  const { user } = useJanua()

  return (
    <UIMFAChallenge
      className={className}
      userEmail={user?.email}
      onVerify={onVerify}
      onUseBackupCode={onUseBackupCode}
      onRequestNewCode={onRequestNewCode}
      onError={onError}
      method={method}
      showBackupCodeOption={showBackupCodeOption}
      allowResend={allowResend}
    />
  )
}
