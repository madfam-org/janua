import React from 'react'
import { render } from '@testing-library/react'
import { SignIn } from './SignIn'

jest.mock('../provider', () => ({
  ...jest.requireActual('../provider'),
  useJanua: () => ({
    signIn: jest.fn(),
    isLoading: false,
    error: null,
  }),
}))

describe('SignIn', () => {
  it('should render without crashing', () => {
    const { container } = render(<SignIn />)
    expect(container.firstChild).toBeTruthy()
  })
})
