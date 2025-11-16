import type { Meta, StoryObj } from '@storybook/react'
import * as React from 'react'
import { SignIn } from './sign-in'

const meta = {
  title: 'Authentication/SignIn',
  component: SignIn,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onSignIn: { action: 'sign in' },
    onSocialSignIn: { action: 'social sign in' },
    onForgotPassword: { action: 'forgot password' },
    onSignUpClick: { action: 'sign up click' },
    onError: { action: 'error' },
  },
} satisfies Meta<typeof SignIn>

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

export const WithoutSignUp: Story = {
  args: {
    showSignUpLink: false,
  },
}

export const WithoutSocialLogin: Story = {
  args: {
    socialProviders: [],
  },
}

export const CustomProviders: Story = {
  args: {
    socialProviders: ['google', 'github'],
  },
}

export const Loading: Story = {
  args: {},
  render: (args) => {
    const [isLoading, setIsLoading] = React.useState(false)
    return (
      <SignIn
        {...args}
        onSignIn={async (email, password) => {
          setIsLoading(true)
          await new Promise((resolve) => setTimeout(resolve, 2000))
          setIsLoading(false)
        }}
      />
    )
  },
}

export const WithError: Story = {
  args: {},
  render: (args) => {
    return (
      <SignIn
        {...args}
        onSignIn={async () => {
          throw new Error('Invalid email or password')
        }}
      />
    )
  },
}
