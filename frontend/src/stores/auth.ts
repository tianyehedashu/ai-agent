/**
 * Auth Store
 *
 * 专门管理认证状态（token、anonymousUserId）的 Zustand Store
 *
 * 设计原则：
 * 1. 单一职责 - 只管理认证相关的状态
 * 2. 持久化 - 使用 zustand/middleware 的 persist 持久化到 localStorage
 * 3. 与 apiClient 解耦 - apiClient 通过 getState() 获取 token，而非直接操作 localStorage
 *
 * 使用方式：
 * - 组件中：useAuthStore((s) => s.token) 选择性订阅
 * - apiClient：useAuthStore.getState().token 直接获取
 *
 * @example
 * ```tsx
 * // 组件中使用
 * const { token, setToken, clearAuth } = useAuthStore()
 *
 * // apiClient 中使用
 * const token = useAuthStore.getState().token
 * ```
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

// 存储 key 常量
const AUTH_STORAGE_KEY = 'auth-storage'

interface AuthState {
  // Token 状态
  token: string | null
  refreshToken: string | null
  anonymousUserId: string | null

  // Token 操作
  setToken: (token: string | null) => void
  setRefreshToken: (token: string | null) => void
  setAnonymousUserId: (id: string | null) => void

  // 清除所有认证信息
  clearAuth: () => void

  // 处理 401 错误（清除 access token，保留 refresh token 供续期）
  handleUnauthorized: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // 初始状态
      token: null,
      refreshToken: null,
      anonymousUserId: null,

      // 设置 JWT Token
      setToken: (token) => {
        set({ token })
      },

      // 设置 Refresh Token
      setRefreshToken: (token) => {
        set({ refreshToken: token })
      },

      // 设置匿名用户 ID
      setAnonymousUserId: (id) => {
        set({ anonymousUserId: id })
      },

      // 清除所有认证信息（用于登出）
      clearAuth: () => {
        set({ token: null, refreshToken: null, anonymousUserId: null })
      },

      // 处理 401 错误
      // 仅清除 access token，保留 refresh token 供 apiClient 自动续期
      handleUnauthorized: () => {
        const { token } = get()
        if (token) {
          console.warn('[AuthStore] Received 401, clearing invalid access token')
          set({ token: null })
        }
      },
    }),
    {
      name: AUTH_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        anonymousUserId: state.anonymousUserId,
      }),
    }
  )
)

// 导出便捷方法，供非 React 环境使用（如 apiClient）
export const getAuthToken = (): string | null => useAuthStore.getState().token
export const getRefreshToken = (): string | null => useAuthStore.getState().refreshToken
export const getAnonymousUserId = (): string | null => useAuthStore.getState().anonymousUserId
export const setAuthToken = (token: string | null): void => {
  useAuthStore.getState().setToken(token)
}
export const setRefreshToken = (token: string | null): void => {
  useAuthStore.getState().setRefreshToken(token)
}
export const setAnonymousUserId = (id: string | null): void => {
  useAuthStore.getState().setAnonymousUserId(id)
}
export const clearAuth = (): void => {
  useAuthStore.getState().clearAuth()
}
export const handleUnauthorized = (): void => {
  useAuthStore.getState().handleUnauthorized()
}
