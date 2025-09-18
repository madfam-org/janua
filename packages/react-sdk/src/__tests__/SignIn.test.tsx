import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SignIn } from '../components/SignIn';
import { PlintoProvider } from '../provider';

const mockSignIn = jest.fn();
const mockRouter = {
  push: jest.fn(),
  replace: jest.fn(),
};

jest.mock('../hooks/usePlinto', () => ({
  usePlinto: () => ({
    signIn: mockSignIn,
    isLoading: false,
    error: null,
  }),
}));

jest.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
}));

describe('SignIn Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const renderSignIn = (props = {}) => {
    return render(
      <PlintoProvider config={{ 
        apiKey: 'test-key',
        tenantId: 'test-tenant',
        baseUrl: 'https://api.plinto.dev' 
      }}>
        <SignIn {...props} />
      </PlintoProvider>
    );
  };

  it('should render sign in form', () => {
    renderSignIn();
    
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('should show forgot password link', () => {
    renderSignIn();
    
    expect(screen.getByText(/forgot password/i)).toBeInTheDocument();
  });

  it('should show sign up link when showSignUp is true', () => {
    renderSignIn({ showSignUp: true });
    
    expect(screen.getByText(/don't have an account/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument();
  });

  it('should not show sign up link when showSignUp is false', () => {
    renderSignIn({ showSignUp: false });
    
    expect(screen.queryByText(/don't have an account/i)).not.toBeInTheDocument();
  });

  it('should validate email format', async () => {
    const user = userEvent.setup();
    renderSignIn();
    
    const emailInput = screen.getByLabelText(/email/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    
    await user.type(emailInput, 'invalid-email');
    await user.click(submitButton);
    
    expect(await screen.findByText(/invalid email/i)).toBeInTheDocument();
    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it('should validate password minimum length', async () => {
    const user = userEvent.setup();
    renderSignIn();
    
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, '123');
    await user.click(submitButton);
    
    expect(await screen.findByText(/password must be at least 8 characters/i)).toBeInTheDocument();
    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it('should handle successful sign in', async () => {
    const user = userEvent.setup();
    const onSuccess = jest.fn();
    
    mockSignIn.mockResolvedValueOnce({
      access_token: 'test-token',
      user: { id: '123', email: 'test@example.com' },
    });
    
    renderSignIn({ onSuccess, redirectUrl: '/dashboard' });
    
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    await user.click(submitButton);
    
    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
      });
    });
    
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith({
        access_token: 'test-token',
        user: { id: '123', email: 'test@example.com' },
      });
    });
    
    expect(mockRouter.push).toHaveBeenCalledWith('/dashboard');
  });

  it('should handle sign in error', async () => {
    const user = userEvent.setup();
    const onError = jest.fn();
    
    mockSignIn.mockRejectedValueOnce(new Error('Invalid credentials'));
    
    renderSignIn({ onError });
    
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'wrongpassword');
    await user.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });
    
    expect(onError).toHaveBeenCalledWith(expect.any(Error));
  });

  it('should show loading state during sign in', async () => {
    const user = userEvent.setup();
    
    mockSignIn.mockImplementation(() => 
      new Promise(resolve => setTimeout(resolve, 100))
    );
    
    renderSignIn();
    
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    await user.click(submitButton);
    
    expect(screen.getByText(/signing in/i)).toBeInTheDocument();
    expect(submitButton).toBeDisabled();
  });

  it('should toggle password visibility', async () => {
    const user = userEvent.setup();
    renderSignIn();
    
    const passwordInput = screen.getByLabelText(/password/i);
    const toggleButton = screen.getByRole('button', { name: /show password/i });
    
    expect(passwordInput).toHaveAttribute('type', 'password');
    
    await user.click(toggleButton);
    expect(passwordInput).toHaveAttribute('type', 'text');
    
    await user.click(toggleButton);
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('should handle remember me checkbox', async () => {
    const user = userEvent.setup();
    renderSignIn();
    
    const rememberCheckbox = screen.getByLabelText(/remember me/i);
    
    expect(rememberCheckbox).not.toBeChecked();
    
    await user.click(rememberCheckbox);
    expect(rememberCheckbox).toBeChecked();
  });

  it('should navigate to forgot password', async () => {
    const user = userEvent.setup();
    renderSignIn();
    
    const forgotLink = screen.getByText(/forgot password/i);
    
    await user.click(forgotLink);
    
    expect(mockRouter.push).toHaveBeenCalledWith('/auth/forgot-password');
  });

  it('should handle social sign in buttons', async () => {
    const user = userEvent.setup();
    const onSocialSignIn = jest.fn();
    
    renderSignIn({ 
      showSocial: true,
      socialProviders: ['google', 'github'],
      onSocialSignIn,
    });
    
    const googleButton = screen.getByRole('button', { name: /sign in with google/i });
    const githubButton = screen.getByRole('button', { name: /sign in with github/i });
    
    expect(googleButton).toBeInTheDocument();
    expect(githubButton).toBeInTheDocument();
    
    await user.click(googleButton);
    expect(onSocialSignIn).toHaveBeenCalledWith('google');
    
    await user.click(githubButton);
    expect(onSocialSignIn).toHaveBeenCalledWith('github');
  });

  it('should apply custom className', () => {
    renderSignIn({ className: 'custom-class' });
    
    const form = screen.getByRole('form');
    expect(form).toHaveClass('custom-class');
  });

  it('should handle Enter key submission', async () => {
    const user = userEvent.setup();
    
    mockSignIn.mockResolvedValueOnce({
      access_token: 'test-token',
    });
    
    renderSignIn();
    
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    await user.keyboard('{Enter}');
    
    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalled();
    });
  });

  it('should clear form on successful sign in', async () => {
    const user = userEvent.setup();
    
    mockSignIn.mockResolvedValueOnce({
      access_token: 'test-token',
    });
    
    renderSignIn();
    
    const emailInput = screen.getByLabelText(/email/i) as HTMLInputElement;
    const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement;
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    await user.click(submitButton);
    
    await waitFor(() => {
      expect(emailInput.value).toBe('');
      expect(passwordInput.value).toBe('');
    });
  });

  it('should handle network errors gracefully', async () => {
    const user = userEvent.setup();
    
    mockSignIn.mockRejectedValueOnce(new Error('Network error'));
    
    renderSignIn();
    
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    await user.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });
  });

  it('should disable form during submission', async () => {
    const user = userEvent.setup();
    
    mockSignIn.mockImplementation(() => 
      new Promise(resolve => setTimeout(resolve, 100))
    );
    
    renderSignIn();
    
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    await user.click(submitButton);
    
    expect(emailInput).toBeDisabled();
    expect(passwordInput).toBeDisabled();
    expect(submitButton).toBeDisabled();
  });
});