import type { Meta, StoryObj } from '@storybook/react'
import { MFASetup } from './mfa-setup'

const meta = {
  title: 'Authentication/MFA/MFASetup',
  component: MFASetup,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onSetupComplete: { action: 'setup complete' },
    onCancel: { action: 'cancel' },
    onError: { action: 'error' },
  },
} satisfies Meta<typeof MFASetup>

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

export const Step1QRCode: Story = {
  args: {
    step: 'setup',
    secret: 'JBSWY3DPEHPK3PXP',
    qrCodeUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  },
}

export const Step2VerifyCode: Story = {
  args: {
    step: 'verify',
    secret: 'JBSWY3DPEHPK3PXP',
  },
}

export const Step3BackupCodes: Story = {
  args: {
    step: 'backup',
    backupCodes: [
      'ABC123DEF456',
      'GHI789JKL012',
      'MNO345PQR678',
      'STU901VWX234',
      'YZA567BCD890',
    ],
  },
}

export const InteractiveFlow: Story = {
  args: {},
  render: (args) => {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground max-w-md">
          This interactive story demonstrates the full MFA setup flow. 
          Click through each step to see the complete experience.
        </p>
        <MFASetup {...args} />
      </div>
    )
  },
}
