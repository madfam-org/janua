import * as React from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { Input } from '../input'
import { Label } from '../label'
import { cn } from '../../lib/utils'

export interface PasswordInputProps {
  id?: string
  value: string
  onChange: (value: string) => void
  label?: string
  placeholder?: string
  disabled?: boolean
  autoComplete?: string
  /** Show password strength meter */
  showStrength?: boolean
  /** Additional actions in the label row (e.g. "Forgot password?" link) */
  labelAction?: React.ReactNode
  className?: string
}

function calculatePasswordStrength(pwd: string): number {
  let strength = 0
  if (pwd.length >= 8) strength += 25
  if (pwd.length >= 12) strength += 25
  if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) strength += 25
  if (/\d/.test(pwd)) strength += 15
  if (/[^a-zA-Z0-9]/.test(pwd)) strength += 10
  return Math.min(strength, 100)
}

export function PasswordInput({
  id = 'password',
  value,
  onChange,
  label = 'Password',
  placeholder = 'Enter your password',
  disabled,
  autoComplete = 'current-password',
  showStrength = false,
  labelAction,
  className,
}: PasswordInputProps) {
  const [showPassword, setShowPassword] = React.useState(false)

  const strength = showStrength ? calculatePasswordStrength(value) : 0
  const strengthLabel = strength >= 75 ? 'Strong' : strength >= 50 ? 'Medium' : 'Weak'
  const strengthColor = strength >= 75 ? 'bg-green-500' : strength >= 50 ? 'bg-yellow-500' : 'bg-red-500'

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between">
        <Label htmlFor={id}>{label}</Label>
        {labelAction}
      </div>
      <div className="relative">
        <Input
          id={id}
          type={showPassword ? 'text' : 'password'}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required
          disabled={disabled}
          autoComplete={autoComplete}
        />
        <button
          type="button"
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => setShowPassword(!showPassword)}
          tabIndex={-1}
          aria-label={showPassword ? 'Hide password' : 'Show password'}
        >
          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>

      {showStrength && value && (
        <div className="space-y-1" style={{ animation: 'janua-slide-up 200ms ease' }}>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Password strength:</span>
            <span className={cn('font-medium', {
              'text-red-500': strength < 50,
              'text-yellow-500': strength >= 50 && strength < 75,
              'text-green-500': strength >= 75,
            })}>
              {strengthLabel}
            </span>
          </div>
          <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
            <div
              className={cn('h-full transition-all duration-300', strengthColor)}
              style={{ width: `${strength}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Use 12+ characters with uppercase, lowercase, numbers, and symbols
          </p>
        </div>
      )}
    </div>
  )
}

/** Exported for consumers who need standalone strength calculation */
export { calculatePasswordStrength }
