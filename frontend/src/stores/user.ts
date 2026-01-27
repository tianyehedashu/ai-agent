/**
 * User Store
 *
 * 管理用户信息的 Zustand Store
 *
 * 职责分离：
 * - authStore: 管理认证状态（token、anonymousUserId）
 * - userStore: 管理用户信息（currentUser、登录/注册/登出操作）
 *
 * 登出时会同时清除 authStore 中的 token
 */

import { create } from 'zustand'

import { userApi, type CurrentUser, type LoginParams, type RegisterParams } from '@/api/user'
import { clearAuth, setAuthToken } from '@/stores/auth'

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
  // 登录成功后，token 由 userApi.login 内部设置到 authStore
  login: async (params) => {
    set({ isLoading: true, error: null })
    try {
      const response = await userApi.login(params)
      // 如果返回的是包含 token 的响应，设置到 authStore
      if ('access_token' in response && typeof response.access_token === 'string') {
        setAuthToken(response.access_token)
      }
      // 获取用户信息
      const user = await userApi.getCurrentUser()
      set({ currentUser: user, isLoading: false, error: null })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '登录失败'
      set({
        currentUser: null,
        isLoading: false,
        error: errorMessage,
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
        error: errorMessage,
      })
      throw error
    }
  },

  // Logout
  // 登出时同时清除 authStore 中的认证信息
  logout: async () => {
    try {
      await userApi.logout()
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '退出登录失败'
      set({ error: errorMessage })
    } finally {
      // 无论成功失败，都清除本地状态
      set({ currentUser: null, error: null })
      // 清除 authStore 中的 token
      clearAuth()
      // 刷新页面以清除所有状态
      window.location.reload()
    }
  },

  // Clear error
  clearError: () => {
    set({ error: null })
  },
}))
