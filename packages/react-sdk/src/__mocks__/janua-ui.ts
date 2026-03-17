// Mock for @janua/ui subpath imports used by react-sdk components
// Only needed for Jest — the actual UI components are provided by @janua/ui at runtime
import React from 'react'

const createMockComponent = (name: string) =>
  React.forwardRef((props: any, ref: any) =>
    React.createElement('div', { ...props, ref, 'data-testid': `mock-${name}` })
  )

export const SignIn = createMockComponent('SignIn')
export const SignUp = createMockComponent('SignUp')
export const UserProfile = createMockComponent('UserProfile')
export const UserButton = createMockComponent('UserButton')
export const OrganizationSwitcher = createMockComponent('OrganizationSwitcher')
export const MFAChallenge = createMockComponent('MFAChallenge')
