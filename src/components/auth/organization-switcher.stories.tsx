import type { Meta, StoryObj } from '@storybook/react'
import { OrganizationSwitcher } from './organization-switcher'

const meta = {
  title: 'Authentication/Organization/OrganizationSwitcher',
  component: OrganizationSwitcher,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onOrganizationChange: { action: 'organization change' },
    onCreateOrganization: { action: 'create organization' },
  },
} satisfies Meta<typeof OrganizationSwitcher>

export default meta
type Story = StoryObj<typeof meta>

const sampleOrganizations = [
  {
    id: '1',
    name: 'Acme Corp',
    slug: 'acme-corp',
    logoUrl: 'https://via.placeholder.com/40?text=AC',
    role: 'admin' as const,
  },
  {
    id: '2',
    name: 'Tech Startup Inc',
    slug: 'tech-startup',
    logoUrl: 'https://via.placeholder.com/40?text=TS',
    role: 'member' as const,
  },
  {
    id: '3',
    name: 'Global Solutions Ltd',
    slug: 'global-solutions',
    role: 'viewer' as const,
  },
]

export const Default: Story = {
  args: {
    organizations: sampleOrganizations,
    currentOrganization: sampleOrganizations[0],
  },
}

export const SingleOrganization: Story = {
  args: {
    organizations: [sampleOrganizations[0]],
    currentOrganization: sampleOrganizations[0],
  },
}

export const ManyOrganizations: Story = {
  args: {
    organizations: [
      ...sampleOrganizations,
      {
        id: '4',
        name: 'Marketing Agency',
        slug: 'marketing-agency',
        role: 'admin' as const,
      },
      {
        id: '5',
        name: 'Consulting Group',
        slug: 'consulting-group',
        role: 'member' as const,
      },
    ],
    currentOrganization: sampleOrganizations[0],
  },
}

export const WithoutCreateButton: Story = {
  args: {
    organizations: sampleOrganizations,
    currentOrganization: sampleOrganizations[0],
    showCreateOrganization: false,
  },
}

export const NoOrganizations: Story = {
  args: {
    organizations: [],
    currentOrganization: undefined,
  },
}

export const DifferentRoles: Story = {
  args: {
    organizations: sampleOrganizations,
    currentOrganization: sampleOrganizations[0],
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Organizations with different roles: Admin, Member, and Viewer
      </p>
      <OrganizationSwitcher {...args} />
    </div>
  ),
}
