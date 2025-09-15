import React from 'react'
import { render, screen } from '@testing-library/react'
import GlobalError from './global-error'

describe('GlobalError', () => {
  it('should render without crashing', () => {
    const mockError = new Error('Test error')
    const mockReset = jest.fn()

    render(<GlobalError error={mockError} reset={mockReset} />)
    expect(screen.getByText('Something went wrong!')).toBeInTheDocument()
  })
})
