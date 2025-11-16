import type { Meta, StoryObj } from '@storybook/react'
import { PhoneVerification } from './phone-verification'

const meta = {
  title: 'Authentication/Profile/PhoneVerification',
  component: PhoneVerification,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onSendCode: { action: 'send code' },
    onVerifyCode: { action: 'verify code' },
    onError: { action: 'error' },
    onComplete: { action: 'complete' },
  },
} satisfies Meta<typeof PhoneVerification>

export default meta
type Story = StoryObj<typeof meta>

export const SendStep: Story = {
  args: {
    phoneNumber: '+1 (555) 123-4567',
    step: 'send',
  },
}

export const VerifyStep: Story = {
  args: {
    phoneNumber: '+1 (555) 123-4567',
    step: 'verify',
  },
}

export const SuccessStep: Story = {
  args: {
    phoneNumber: '+1 (555) 123-4567',
    step: 'success',
  },
}

export const WithLogo: Story = {
  args: {
    phoneNumber: '+1 (555) 123-4567',
    step: 'send',
    logoUrl: 'https://via.placeholder.com/150x40?text=Logo',
  },
}

export const InternationalNumber: Story = {
  args: {
    phoneNumber: '+44 20 7123 4567',
    step: 'send',
  },
}

export const AutoSubmitDemo: Story = {
  args: {
    phoneNumber: '+1 (555) 123-4567',
    step: 'verify',
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Enter a 6-digit code to see auto-submit in action
      </p>
      <PhoneVerification {...args} />
    </div>
  ),
}

export const FullFlow: Story = {
  args: {
    phoneNumber: '+1 (555) 123-4567',
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Complete phone verification flow: Send Code → Verify → Success
      </p>
      <PhoneVerification {...args} />
    </div>
  ),
}
