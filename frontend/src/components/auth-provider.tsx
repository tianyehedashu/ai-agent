/**
 * Auth Provider
 *
 * 应用初始化时先完成身份校验（GET /auth/me），再渲染子组件。
 *
 * 设计要点：
 * 1. 使用 TanStack Query 与项目其他数据获取保持一致
 * 2. 阻塞渲染直到身份校验完成
 * 3. 监听 token 过期事件，自动 toast 提示并重定向到登录页
 * 4. 未认证用户：local 模式重定向到 /login；sso 模式整页跳转到 giikin 单点登录入口
 *
 * 注意：currentUser 的唯一数据源是 TanStack Query 缓存（queryKey: ['auth','currentUser']），
 * 子组件通过 useCurrentUser() 读取，无需 Zustand store 中转。
 */

import { type ReactNode, useEffect, useRef, useState } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, useLocation } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import {
  clearSsoAttempt,
  clearStaleGiikinSession,
  getSsoAttemptCount,
  initiateSsoLogin,
  isHybridMode,
  isSsoMode,
  isWithinSsoCooldown,
  SSO_MAX_ATTEMPTS,
} from '@/config/auth'
import { useToast } from '@/hooks/use-toast'
import { AlertCircle, Loader2 } from '@/lib/lucide-icons'
import { getAuthToken, useAuthHydrated } from '@/stores/auth'
import { CURRENT_USER_QUERY_KEY, currentUserQueryOptions } from '@/stores/user'

const PUBLIC_PATHS = ['/login', '/register', '/sso-callback']

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: Readonly<AuthProviderProps>): React.JSX.Element {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const location = useLocation()
  const ssoRedirectStarted = useRef(false)
  const ssoPostLoginRetryDone = useRef(false)
  const ssoStaleRecoveryStarted = useRef(false)
  const [ssoRedirectFailed, setSsoRedirectFailed] = useState(false)
  const [ssoPostLoginRetrying, setSsoPostLoginRetrying] = useState(false)
  const [ssoStaleRecovering, setSsoStaleRecovering] = useState(false)

  const isOnSsoCallback = location.pathname === '/sso-callback'
  const isOnPublicPath = PUBLIC_PATHS.includes(location.pathname)
  /**
   * 公开页跳过 auth/me：
   * - /sso-callback 由 SsoCallbackPage 自行换票与重试，避免抢先 401 触发冷却期
   * - /login、/register 不受守卫保护，无需提前校验身份（即便已登录也由各页面自行判断）
   */
  const deferAuthMe = isOnSsoCallback || isOnPublicPath
  const authHydrated = useAuthHydrated()

  const {
    data: currentUser,
    isLoading,
    isFetched,
    error,
    refetch,
  } = useQuery({
    ...currentUserQueryOptions,
    enabled: !deferAuthMe && authHydrated,
  })

  /** 仅 auth/me 的 401 表示会话无效；业务接口 403 不影响全局登录态 */
  const isSessionInvalid = error instanceof ApiError && error.status === 401
  const sessionUser = isSessionInvalid ? null : (currentUser ?? null)

  // 监听 token 过期事件（由 apiClient 在 401 + 有旧 token 时发出）
  useEffect(() => {
    const handler = (): void => {
      toast({
        variant: 'destructive',
        title: '登录已过期',
        description: '请重新登录以恢复数据访问',
      })
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null)
      void queryClient.invalidateQueries()
      void refetch()
    }
    window.addEventListener('auth:session-expired', handler)
    return () => {
      window.removeEventListener('auth:session-expired', handler)
    }
  }, [toast, queryClient, refetch])

  // SSO 登录成功后清除重试计数
  useEffect(() => {
    if (isFetched && sessionUser) {
      clearSsoAttempt()
    }
  }, [sessionUser, isFetched])

  // SSO 回调后 guard_token 写入存在短延迟，冷却期内先重试 auth/me 再报错
  // hybrid + 有本地 JWT 时跳过此 effect：JWT 过期应走 /login 而非 SSO 自愈
  useEffect(() => {
    if (!isSsoMode || !isWithinSsoCooldown() || ssoPostLoginRetryDone.current || deferAuthMe) {
      return
    }
    if (isHybridMode && !!getAuthToken()) {
      return
    }
    if (!isSessionInvalid || sessionUser) {
      return
    }
    const attemptCount = getSsoAttemptCount()
    console.warn(
      `[SSO] AuthProvider cooldown retry, attemptCount=${String(attemptCount)}/${String(SSO_MAX_ATTEMPTS)}`
    )
    if (attemptCount >= SSO_MAX_ATTEMPTS) {
      // 断路器触发：不再自动重试，直接展示错误页
      return
    }
    ssoPostLoginRetryDone.current = true
    setSsoPostLoginRetrying(true)
    void (async () => {
      for (let attempt = 0; attempt < 8; attempt += 1) {
        await queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY })
        const result = await refetch()
        if (result.data) {
          clearSsoAttempt()
          setSsoPostLoginRetrying(false)
          return
        }
        await new Promise((resolve) => {
          setTimeout(resolve, 500)
        })
      }
      setSsoPostLoginRetrying(false)
      if (ssoStaleRecoveryStarted.current) {
        return
      }
      ssoStaleRecoveryStarted.current = true
      setSsoStaleRecovering(true)
      await clearStaleGiikinSession()
      clearSsoAttempt()
      ssoRedirectStarted.current = false
      try {
        await initiateSsoLogin(location.pathname)
      } catch (err: unknown) {
        setSsoStaleRecovering(false)
        const message = err instanceof Error ? err.message : 'SSO 登录初始化失败'
        toast({
          variant: 'destructive',
          title: '登录已过期',
          description: message,
        })
      }
    })()
  }, [deferAuthMe, isSessionInvalid, location.pathname, queryClient, refetch, sessionUser, toast])

  const ssoCooldownActive = isWithinSsoCooldown()
  /**
   * hybrid 模式下，若本地有 JWT token 说明用户已通过邮箱登录，
   * 不应自动跳 SSO（JWT 过期走 refresh 机制，而非 SSO 重定向）。
   */
  const hasLocalJwt = !!getAuthToken()
  const ssoAttemptCount = getSsoAttemptCount()
  const shouldStartSso =
    isSsoMode &&
    !sessionUser &&
    isFetched &&
    !isOnPublicPath &&
    isSessionInvalid &&
    !ssoCooldownActive &&
    ssoAttemptCount < SSO_MAX_ATTEMPTS &&
    !(isHybridMode && hasLocalJwt)

  useEffect(() => {
    if (!shouldStartSso || ssoRedirectStarted.current) {
      return
    }
    ssoRedirectStarted.current = true
    void initiateSsoLogin(location.pathname).catch((err: unknown) => {
      ssoRedirectStarted.current = false
      setSsoRedirectFailed(true)
      const message = err instanceof Error ? err.message : 'SSO 登录初始化失败'
      toast({
        variant: 'destructive',
        title: '无法跳转 SSO 登录',
        description: message,
      })
    })
  }, [shouldStartSso, location.pathname, toast])

  if ((!authHydrated || isLoading) && !deferAuthMe) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">正在加载...</p>
        </div>
      </div>
    )
  }

  // 严重错误状态（如服务不可用）- auth/me 的 401 走下方 SSO / 登录重定向
  if (error && !isSessionInvalid) {
    const detail =
      error instanceof ApiError && error.status === 404
        ? 'API 路径不存在，请确认后端 ROOT_PATH 与前端 VITE_APP_ROOT 一致（默认 /ai-agent），并重启 make dev'
        : '无法连接到服务器，请检查网络连接'
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <div>
            <p className="font-medium text-foreground">连接失败</p>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">{detail}</p>
          </div>
          <button
            onClick={() => refetch()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            重试
          </button>
        </div>
      </div>
    )
  }

  // 未认证 + 不在公开页面
  if (!sessionUser && isFetched && !isOnPublicPath) {
    if (isSsoMode && isSessionInvalid && ssoCooldownActive) {
      if (ssoPostLoginRetrying || ssoStaleRecovering) {
        return (
          <div className="flex h-screen items-center justify-center bg-background">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {ssoStaleRecovering ? '登录已过期，正在重新登录…' : '正在确认登录态...'}
              </p>
            </div>
          </div>
        )
      }
      return (
        <div className="flex h-screen items-center justify-center bg-background">
          <div className="flex flex-col items-center gap-4 text-center">
            <AlertCircle className="h-12 w-12 text-destructive" />
            <div>
              <p className="font-medium text-foreground">登录已过期</p>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                浏览器中的登录凭证已失效。请重新登录；若仍失败，请联系管理员检查网关
                giikin-auth-bridge 配置（见 docs/SSO.md）。
              </p>
            </div>
            <button
              onClick={() => {
                void (async () => {
                  await clearStaleGiikinSession()
                  clearSsoAttempt()
                  ssoRedirectStarted.current = false
                  ssoStaleRecoveryStarted.current = false
                  ssoPostLoginRetryDone.current = false
                  await initiateSsoLogin(location.pathname)
                })()
              }}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              重新登录
            </button>
          </div>
        </div>
      )
    }
    if (isSsoMode) {
      if (ssoRedirectFailed) {
        return (
          <div className="flex h-screen items-center justify-center bg-background">
            <div className="flex flex-col items-center gap-4 text-center">
              <AlertCircle className="h-12 w-12 text-destructive" />
              <p className="font-medium text-foreground">SSO 登录跳转失败</p>
              <button
                onClick={() => {
                  setSsoRedirectFailed(false)
                  ssoRedirectStarted.current = false
                }}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                重试
              </button>
            </div>
          </div>
        )
      }
      // 断路器触发：连续多次 SSO 登录均失败，停止自动重定向，展示手动重试页
      if (ssoAttemptCount >= SSO_MAX_ATTEMPTS) {
        return (
          <div className="flex h-screen items-center justify-center bg-background">
            <div className="flex flex-col items-center gap-4 text-center">
              <AlertCircle className="h-12 w-12 text-destructive" />
              <div>
                <p className="font-medium text-foreground">登录已过期</p>
                <p className="mt-1 max-w-md text-sm text-muted-foreground">
                  连续 {String(SSO_MAX_ATTEMPTS)} 次单点登录后仍无法获取身份，可能是 guard_token
                  Cookie 未正确设置。 请联系管理员检查 HiGress giikin-auth-bridge 配置。
                </p>
              </div>
              <button
                onClick={() => {
                  void (async () => {
                    await clearStaleGiikinSession()
                    clearSsoAttempt()
                    ssoRedirectStarted.current = false
                    ssoStaleRecoveryStarted.current = false
                    ssoPostLoginRetryDone.current = false
                    await initiateSsoLogin(location.pathname)
                  })()
                }}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                重新登录
              </button>
            </div>
          </div>
        )
      }
      // hybrid 模式下有本地 JWT 但已过期 → 跳登录页（用户可选 SSO 或邮箱重新登录）
      if (isHybridMode && hasLocalJwt) {
        return <Navigate to="/login" state={{ from: location.pathname }} replace />
      }
      return (
        <div className="flex h-screen items-center justify-center bg-background">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">正在跳转 SSO 登录...</p>
          </div>
        </div>
      )
    }
    // local 模式：重定向到本地登录页（保留原始路径以便登录后跳回）
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  return <>{children}</>
}
