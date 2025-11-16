import type { Meta, StoryObj } from '@storybook/react'
import { PasswordReset } from './password-reset'

const meta = {
  title: 'Authentication/Profile/PasswordReset',
  component: PasswordReset,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onRequestReset: { action: 'request reset' },
    onVerifyToken: { action: 'verify token' },
    onResetPassword: { action: 'reset password' },
    onError: { action: 'error' },
    onBackToSignIn: { action: 'back to sign in' },
  },
} satisfies Meta<typeof PasswordReset>

export default meta
type Story = StoryObj<typeof meta>

export const RequestStep: Story = {
  args: {
    step: 'request',
  },
}

export const VerifyStep: Story = {
  args: {
    step: 'verify',
    email: 'john@example.com',
  },
}

export const ResetStep: Story = {
  args: {
    step: 'reset',
    token: 'sample-token-123',
  },
}

export const SuccessStep: Story = {
  args: {
    step: 'success',
  },
}

export const WithLogo: Story = {
  args: {
    step: 'request',
    logoUrl: 'https://via.placeholder.com/150x40?text=Logo',
  },
}

export const PasswordStrengthDemo: Story = {
  args: {
    step: 'reset',
    token: 'sample-token-123',
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Try different passwords to see the strength meter:
        <br />• Weak: short or simple passwords
        <br />• Medium: 8+ chars with mixed case
        <br />• Strong: 12+ chars with numbers & symbols
      </p>
      <PasswordReset {...args} />
    </div>
  ),
}

export const FullFlow: Story = {
  args: {},
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Complete password reset flow: Request → Email Sent → Reset → Success
      </p>
      <PasswordReset {...args} />
    </div>
  ),
}
