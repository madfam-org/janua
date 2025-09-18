import { usePlinto } from '../provider'

export function useAuth() {
  const { user, session, isLoading, isAuthenticated, signIn, signOut } = usePlinto()
  
  return {
    user,
    session,
    isLoading,
    isAuthenticated,
    signIn,
    signOut,
  }
}