import type { Meta, StoryObj } from '@storybook/react'
import { EmailVerification } from './email-verification'

const meta = {
  title: 'Authentication/Profile/EmailVerification',
  component: EmailVerification,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onVerify: { action: 'verify' },
    onResendEmail: { action: 'resend email' },
    onError: { action: 'error' },
    onComplete: { action: 'complete' },
  },
} satisfies Meta<typeof EmailVerification>

export default meta
type Story = StoryObj<typeof meta>

export const PendingState: Story = {
  args: {
    email: 'john@example.com',
    status: 'pending',
  },
}

export const VerifyingState: Story = {
  args: {
    email: 'john@example.com',
    status: 'verifying',
  },
}

export const SuccessState: Story = {
  args: {
    email: 'john@example.com',
    status: 'success',
  },
}

export const ErrorState: Story = {
  args: {
    email: 'john@example.com',
    status: 'error',
  },
}

export const WithLogo: Story = {
  args: {
    email: 'john@example.com',
    status: 'pending',
    logoUrl: 'https://via.placeholder.com/150x40?text=Logo',
  },
}

export const WithResend: Story = {
  args: {
    email: 'john@example.com',
    status: 'pending',
    showResend: true,
  },
}

export const WithoutResend: Story = {
  args: {
    email: 'john@example.com',
    status: 'pending',
    showResend: false,
  },
}

export const AutoVerifyDemo: Story = {
  args: {
    email: 'john@example.com',
    token: 'sample-verification-token-123',
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        This demonstrates automatic verification when a token is provided (e.g., from email link)
      </p>
      <EmailVerification {...args} />
    </div>
  ),
}
