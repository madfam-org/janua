import type { Meta, StoryObj } from '@storybook/react'
import { BackupCodes } from './backup-codes'

const meta = {
  title: 'Authentication/MFA/BackupCodes',
  component: BackupCodes,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onRegenerate: { action: 'regenerate' },
    onDownload: { action: 'download' },
    onClose: { action: 'close' },
    onError: { action: 'error' },
  },
} satisfies Meta<typeof BackupCodes>

export default meta
type Story = StoryObj<typeof meta>

const sampleCodes = [
  'ABC123DEF456',
  'GHI789JKL012',
  'MNO345PQR678',
  'STU901VWX234',
  'YZA567BCD890',
  'CDE123FGH456',
  'IJK789LMN012',
  'OPQ345RST678',
]

export const Default: Story = {
  args: {
    codes: sampleCodes,
  },
}

export const WithLogo: Story = {
  args: {
    codes: sampleCodes,
    logoUrl: 'https://via.placeholder.com/150x40?text=Logo',
  },
}

export const FewCodesRemaining: Story = {
  args: {
    codes: ['ABC123DEF456', 'GHI789JKL012'],
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-yellow-600 max-w-md">
        ⚠️ Only 2 backup codes remaining - consider regenerating
      </p>
      <BackupCodes {...args} />
    </div>
  ),
}

export const SingleCodeLeft: Story = {
  args: {
    codes: ['ABC123DEF456'],
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-red-600 max-w-md">
        🚨 Critical: Only 1 backup code remaining - regenerate immediately
      </p>
      <BackupCodes {...args} />
    </div>
  ),
}

export const AllCodesAvailable: Story = {
  args: {
    codes: sampleCodes,
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-green-600 max-w-md">
        ✅ All {sampleCodes.length} backup codes available
      </p>
      <BackupCodes {...args} />
    </div>
  ),
}
