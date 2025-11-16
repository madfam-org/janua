import type { Meta, StoryObj } from '@storybook/react'
import { UserButton } from './user-button'

const meta = {
  title: 'Authentication/UserButton',
  component: UserButton,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onProfileClick: { action: 'profile click' },
    onSettingsClick: { action: 'settings click' },
    onSignOutClick: { action: 'sign out click' },
  },
} satisfies Meta<typeof UserButton>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    user: {
      name: 'John Doe',
      email: 'john@example.com',
      imageUrl: 'https://via.placeholder.com/40',
    },
  },
}

export const WithoutAvatar: Story = {
  args: {
    user: {
      name: 'Jane Smith',
      email: 'jane@example.com',
    },
  },
}

export const LongName: Story = {
  args: {
    user: {
      name: 'Alexander Christopher Wellington III',
      email: 'alexander.wellington@example.com',
    },
  },
}

export const WithInitials: Story = {
  args: {
    user: {
      name: 'Alice Brown',
      email: 'alice@example.com',
    },
  },
}

export const CustomMenuItems: Story = {
  args: {
    user: {
      name: 'Bob Wilson',
      email: 'bob@example.com',
    },
    showSettings: true,
  },
}

export const MinimalMenu: Story = {
  args: {
    user: {
      name: 'Carol Davis',
      email: 'carol@example.com',
    },
    showSettings: false,
  },
}
