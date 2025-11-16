import type { Meta, StoryObj } from '@storybook/react'
import { UserProfile } from './user-profile'

const meta = {
  title: 'Authentication/Profile/UserProfile',
  component: UserProfile,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onUpdateProfile: { action: 'update profile' },
    onUploadAvatar: { action: 'upload avatar' },
    onUpdateEmail: { action: 'update email' },
    onUpdatePassword: { action: 'update password' },
    onToggleMFA: { action: 'toggle MFA' },
    onDeleteAccount: { action: 'delete account' },
    onError: { action: 'error' },
  },
} satisfies Meta<typeof UserProfile>

export default meta
type Story = StoryObj<typeof meta>

const sampleUser = {
  id: 'user-123',
  email: 'john.doe@example.com',
  firstName: 'John',
  lastName: 'Doe',
  username: 'johndoe',
  avatarUrl: 'https://via.placeholder.com/80?text=JD',
  phone: '+1 (555) 123-4567',
  emailVerified: true,
  phoneVerified: true,
  twoFactorEnabled: false,
  createdAt: new Date('2024-01-15'),
}

export const Default: Story = {
  args: {
    user: sampleUser,
  },
}

export const WithoutAvatar: Story = {
  args: {
    user: {
      ...sampleUser,
      avatarUrl: undefined,
    },
  },
}

export const UnverifiedContact: Story = {
  args: {
    user: {
      ...sampleUser,
      emailVerified: false,
      phoneVerified: false,
    },
  },
}

export const WithMFAEnabled: Story = {
  args: {
    user: {
      ...sampleUser,
      twoFactorEnabled: true,
    },
  },
}

export const MinimalProfile: Story = {
  args: {
    user: {
      id: 'user-456',
      email: 'jane@example.com',
      emailVerified: true,
    },
  },
}

export const CompleteProfile: Story = {
  args: {
    user: sampleUser,
    showSecurityTab: true,
    showDangerZone: true,
  },
}

export const SecurityTabOnly: Story = {
  args: {
    user: sampleUser,
    showSecurityTab: true,
    showDangerZone: false,
  },
}

export const NoDangerZone: Story = {
  args: {
    user: sampleUser,
    showSecurityTab: true,
    showDangerZone: false,
  },
}
