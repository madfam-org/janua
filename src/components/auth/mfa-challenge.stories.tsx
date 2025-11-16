import type { Meta, StoryObj } from '@storybook/react'
import { MFAChallenge } from './mfa-challenge'

const meta = {
  title: 'Authentication/MFA/MFAChallenge',
  component: MFAChallenge,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onVerify: { action: 'verify' },
    onUseBackupCode: { action: 'use backup code' },
    onCancel: { action: 'cancel' },
    onError: { action: 'error' },
  },
} satisfies Meta<typeof MFAChallenge>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {},
}

export const WithLogo: Story = {
  args: {
    logoUrl: 'https://via.placeholder.com/150x40?text=Logo',
  },
}

export const WithBackupCode: Story = {
  args: {
    allowBackupCode: true,
  },
}

export const WithoutBackupCode: Story = {
  args: {
    allowBackupCode: false,
  },
}

export const WithError: Story = {
  args: {},
  render: (args) => (
    <MFAChallenge
      {...args}
      onVerify={async () => {
        throw new Error('Invalid verification code. Please try again.')
      }}
    />
  ),
}

export const AutoSubmitDemo: Story = {
  args: {
    allowBackupCode: true,
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Enter a 6-digit code to see auto-submit in action
      </p>
      <MFAChallenge {...args} />
    </div>
  ),
}
