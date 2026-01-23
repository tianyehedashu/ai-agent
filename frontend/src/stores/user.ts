import { create } from 'zustand'

import { userApi, type CurrentUser, type LoginParams, type RegisterParams } from '@/api/user'

interface UserState {
  // Current user
  currentUser: CurrentUser | null
  isLoading: boolean
  error: string | null

  // Actions
  setCurrentUser: (user: CurrentUser | null) => void
  login: (params: LoginParams) => Promise<void>
  register: (params: RegisterParams) => Promise<void>
  logout: () => Promise<void>
  clearError: () => void
}

export const useUserStore = create<UserState>((set) => ({
  // Initial state
  currentUser: null,
  isLoading: false,
  error: null,

  // Set current user (由 AuthProvider 通过 TanStack Query 同步)
  setCurrentUser: (user) => {
    set({ currentUser: user, error: null })
  },

  // Login
  login: async (params) => {
    set({ isLoading: true, error: null })
    try {
      const user = await userApi.login(params)
      set({ currentUser: user, isLoading: false, error: null })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '登录失败'
      set({ 
        currentUser: null, 
        isLoading: false, 
        error: errorMessage 
      })
      throw error // Re-throw to allow component to handle specific errors/redirects
    }
  },

  // Register
  register: async (params) => {
    set({ isLoading: true, error: null })
    try {
      const user = await userApi.register(params)
      set({ currentUser: user, isLoading: false, error: null })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '注册失败'
      set({ 
        currentUser: null, 
        isLoading: false, 
        error: errorMessage 
      })
      throw error
    }
  },

  // Logout
  logout: async () => {
    try {
      await userApi.logout()
      set({ currentUser: null, error: null })
      // 刷新页面以清除所有状态
      window.location.reload()
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '退出登录失败'
      set({ error: errorMessage })
      // 即使出错也清除本地状态
      set({ currentUser: null })
      window.location.reload()
    }
  },

  // Clear error
  clearError: () => {
    set({ error: null })
  },
}))