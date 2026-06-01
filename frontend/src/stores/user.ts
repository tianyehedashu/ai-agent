/**
 * User Store
 *
 * 管理用户信息的 Zustand Store
 *
 * 职责分离：
 * - authStore: 管理认证状态（token）
 * - userStore: 管理用户信息（currentUser、登录/注册/登出操作）
 *
 * 登出时会同时清除 authStore 中的 token
 */

import { create } from 'zustand'

import { userApi, type CurrentUser, type LoginParams, type RegisterParams } from '@/api/user'
import { clearSsoAttempt, isSsoMode, resolveSsoLogoutUrl } from '@/config/auth'
import { clearAuth, setAuthToken } from '@/stores/auth'

function appRootPath(): string {
  const root = (import.meta.env.VITE_APP_ROOT as string | undefined) ?? '/ai-agent'
  if (!root || root === '/') {
    return '/'
  }
  return root.endsWith('/') ? root.slice(0, -1) : root
}

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
  // local：清 JWT；sso：须调 IAM /api/auth/logout 清除 guard_token，否则刷新后仍登录
  logout: async () => {
    try {
      if (isSsoMode) {
        const response = await fetch(resolveSsoLogoutUrl(), {
          method: 'POST',
          credentials: 'include',
        })
        if (!response.ok) {
          console.warn('[SSO logout] IAM logout failed:', response.status, response.statusText)
        }
      } else {
        await userApi.logout()
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '退出登录失败'
      console.warn('[logout]', errorMessage, error)
      set({ error: errorMessage })
    } finally {
      clearSsoAttempt()
      set({ currentUser: null, error: null })
      clearAuth()
      if (isSsoMode) {
        window.location.href = `${appRootPath()}/login`
      } else {
        window.location.reload()
      }
    }
  },

  // Clear error
  clearError: () => {
    set({ error: null })
  },
}))
