/**
 * User Store & useCurrentUser Hook
 *
 * 架构：TanStack Query 是 currentUser 的唯一数据源，Zustand store 仅保留命令式操作。
 *
 * 职责分离：
 * - useCurrentUser(): 读取当前用户（派生自 TanStack Query 缓存，无 effect 同步）
 * - useUserStore: login / register / logout 等命令式操作
 * - authStore: 管理 token 持久化
 */

import { useQuery } from '@tanstack/react-query'
import { create } from 'zustand'

import { ApiError } from '@/api/errors'
import { userApi, type CurrentUser, type LoginParams, type RegisterParams } from '@/api/user'
import { clearSsoAttempt, isHybridMode, isSsoMode, resolveSsoLogoutUrl } from '@/config/auth'
import { clearAuth } from '@/stores/auth'

// ---------------------------------------------------------------------------
// useCurrentUser — TanStack Query 单一数据源
// ---------------------------------------------------------------------------

/** auth/me 查询的 queryKey，全局共享 */
export const CURRENT_USER_QUERY_KEY = ['auth', 'currentUser'] as const

/**
 * 读取当前登录用户。
 *
 * - 数据源：TanStack Query 缓存（与 AuthProvider 共享同一 queryKey）
 * - 401 视为会话无效，返回 null
 * - 未 fetch 或 loading 时返回 null
 */
export function useCurrentUser(): CurrentUser | null {
  const { data, error } = useQuery({
    queryKey: CURRENT_USER_QUERY_KEY,
    queryFn: () => userApi.getCurrentUser(),
    staleTime: 1000 * 60 * 5,
  })

  const isSessionInvalid = error instanceof ApiError && error.status === 401
  return isSessionInvalid ? null : (data ?? null)
}

// ---------------------------------------------------------------------------
// User Store — 仅保留命令式操作
// ---------------------------------------------------------------------------

function appRootPath(): string {
  const root = (import.meta.env.VITE_APP_ROOT as string | undefined) ?? '/ai-agent'
  if (!root || root === '/') {
    return '/'
  }
  return root.endsWith('/') ? root.slice(0, -1) : root
}

interface UserState {
  // Actions
  login: (params: LoginParams) => Promise<CurrentUser>
  register: (params: RegisterParams) => Promise<CurrentUser>
  logout: () => Promise<void>
}

export const useUserStore = create<UserState>(() => ({
  // Login
  login: async (params) => {
    // userApi.login 内部已通过 apiClient.setToken 设置 token
    const user = await userApi.login(params)
    return user
  },

  // Register
  register: async (params) => {
    const user = await userApi.register(params)
    return user
  },

  // Logout
  // local：清 JWT；sso：须调 IAM /api/auth/logout 清除 guard_token
  // hybrid：同时清 JWT + 调 IAM logout，确保切换身份时状态干净
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
      }
      if (!isSsoMode || isHybridMode) {
        await userApi.logout()
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '退出登录失败'
      console.warn('[logout]', errorMessage, error)
    } finally {
      clearSsoAttempt()
      clearAuth()
      if (isSsoMode) {
        window.location.href = `${appRootPath()}/login`
      } else {
        window.location.reload()
      }
    }
  },
}))
