import type { Meta, StoryObj } from '@storybook/react'
import { OrganizationProfile } from './organization-profile'

const meta = {
  title: 'Authentication/Organization/OrganizationProfile',
  component: OrganizationProfile,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onUpdateOrganization: { action: 'update organization' },
    onUploadLogo: { action: 'upload logo' },
    onInviteMember: { action: 'invite member' },
    onRemoveMember: { action: 'remove member' },
    onUpdateRole: { action: 'update role' },
    onLeaveOrganization: { action: 'leave organization' },
    onDeleteOrganization: { action: 'delete organization' },
    onError: { action: 'error' },
  },
} satisfies Meta<typeof OrganizationProfile>

export default meta
type Story = StoryObj<typeof meta>

const sampleOrganization = {
  id: '1',
  name: 'Acme Corp',
  slug: 'acme-corp',
  logoUrl: 'https://via.placeholder.com/80?text=AC',
  description: 'Building the future of software',
  website: 'https://acme-corp.example.com',
  createdAt: new Date('2024-01-15'),
}

const sampleMembers = [
  {
    id: '1',
    userId: 'user-1',
    email: 'john@acme-corp.com',
    name: 'John Doe',
    role: 'admin' as const,
    avatarUrl: 'https://via.placeholder.com/40?text=JD',
    joinedAt: new Date('2024-01-15'),
  },
  {
    id: '2',
    userId: 'user-2',
    email: 'jane@acme-corp.com',
    name: 'Jane Smith',
    role: 'member' as const,
    avatarUrl: 'https://via.placeholder.com/40?text=JS',
    joinedAt: new Date('2024-02-01'),
  },
  {
    id: '3',
    userId: 'user-3',
    email: 'bob@external.com',
    name: 'Bob Wilson',
    role: 'viewer' as const,
    joinedAt: new Date('2024-03-10'),
  },
]

export const AdminView: Story = {
  args: {
    organization: sampleOrganization,
    members: sampleMembers,
    currentUserRole: 'admin',
  },
}

export const MemberView: Story = {
  args: {
    organization: sampleOrganization,
    members: sampleMembers,
    currentUserRole: 'member',
  },
}

export const ViewerView: Story = {
  args: {
    organization: sampleOrganization,
    members: sampleMembers,
    currentUserRole: 'viewer',
  },
}

export const SmallTeam: Story = {
  args: {
    organization: sampleOrganization,
    members: [sampleMembers[0], sampleMembers[1]],
    currentUserRole: 'admin',
  },
}

export const LargeTeam: Story = {
  args: {
    organization: sampleOrganization,
    members: [
      ...sampleMembers,
      {
        id: '4',
        userId: 'user-4',
        email: 'alice@acme-corp.com',
        name: 'Alice Brown',
        role: 'member' as const,
        joinedAt: new Date('2024-03-15'),
      },
      {
        id: '5',
        userId: 'user-5',
        email: 'charlie@acme-corp.com',
        name: 'Charlie Davis',
        role: 'member' as const,
        joinedAt: new Date('2024-04-01'),
      },
    ],
    currentUserRole: 'admin',
  },
}

export const NoMembers: Story = {
  args: {
    organization: sampleOrganization,
    members: [sampleMembers[0]], // Just the current admin
    currentUserRole: 'admin',
  },
}

export const WithDangerZone: Story = {
  args: {
    organization: sampleOrganization,
    members: sampleMembers,
    currentUserRole: 'admin',
    showDangerZone: true,
  },
}
