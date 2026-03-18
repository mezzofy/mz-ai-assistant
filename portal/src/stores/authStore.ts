import { create } from 'zustand'
import type { AuthState } from '../types'

interface AuthStore extends AuthState {
  setAuth: (token: string, user: AuthState['user']) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthStore>((set) => ({
  access_token: null,
  user: null,
  isAuthenticated: false,
  setAuth: (token, user) => set({ access_token: token, user, isAuthenticated: true }),
  clearAuth: () => set({ access_token: null, user: null, isAuthenticated: false }),
}))
