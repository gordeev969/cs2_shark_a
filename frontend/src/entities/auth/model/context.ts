import { createContext, useContext } from 'react'
import type { AuthSession } from '@/shared/api/contracts'
export interface AuthState extends AuthSession {
  refresh: () => Promise<void>
}
export const AuthContext = createContext<AuthState | null>(null)
export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider is required')
  return value
}
