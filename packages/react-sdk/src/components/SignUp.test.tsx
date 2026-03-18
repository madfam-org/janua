import React from 'react'
import { render } from '@testing-library/react'
import { SignUp } from './SignUp'

jest.mock('../provider', () => ({
  ...jest.requireActual('../provider'),
  useJanua: () => ({
    signUp: jest.fn(),
    isLoading: false,
    error: null,
  }),
}))

describe('SignUp', () => {
  it('should render without crashing', () => {
    const { container } = render(<SignUp />)
    expect(container.firstChild).toBeTruthy()
  })
})
