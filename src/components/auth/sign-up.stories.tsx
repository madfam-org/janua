import type { Meta, StoryObj } from '@storybook/react'
import { SignUp } from './sign-up'

const meta = {
  title: 'Authentication/SignUp',
  component: SignUp,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onSignUp: { action: 'sign up' },
    onSocialSignUp: { action: 'social sign up' },
    onSignInClick: { action: 'sign in click' },
    onError: { action: 'error' },
  },
} satisfies Meta<typeof SignUp>

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

export const WithoutSignIn: Story = {
  args: {
    showSignInLink: false,
  },
}

export const WithoutSocialSignUp: Story = {
  args: {
    socialProviders: [],
  },
}

export const CustomProviders: Story = {
  args: {
    socialProviders: ['google', 'github'],
  },
}

export const WithTerms: Story = {
  args: {
    termsUrl: 'https://example.com/terms',
    privacyUrl: 'https://example.com/privacy',
  },
}

export const PasswordStrengthDemo: Story = {
  args: {},
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Try different passwords to see the strength meter in action
      </p>
      <SignUp {...args} />
    </div>
  ),
}
