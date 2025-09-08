import { usePlinto } from '../provider'

export function useAuth() {
  const { identity, session, isLoading, isAuthenticated, signIn, signOut } = usePlinto()
  
  return {
    user: identity,
    session,
    isLoading,
    isAuthenticated,
    signIn,
    signOut,
  }
}