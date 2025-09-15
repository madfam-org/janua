import React from 'react'
import { render, screen } from '@testing-library/react'
import Error from './error'

describe('Error', () => {
  it('should render without crashing', () => {
    const mockError = new Error('Test error')
    const mockReset = jest.fn()

    render(<Error error={mockError} reset={mockReset} />)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })
})
