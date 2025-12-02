import React from 'react';
import { render, screen } from '@testing-library/react';
import { DemoBanner } from './demo-banner';

describe('DemoBanner', () => {
  it('should render without crashing', () => {
    render(<DemoBanner />);
    expect(screen.getByTestId('demo-banner')).toBeInTheDocument();
  });
  
  it('should have correct props', () => {
    const { container } = render(<demo-banner />);
    expect(container.firstChild).toBeTruthy();
  });
  
  // TODO: Add more specific tests based on component functionality
});
