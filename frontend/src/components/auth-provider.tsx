/**
 * Auth Provider
 *
 * 应用初始化时先完成身份校验（GET /auth/me），再渲染子组件。
 *
 * 设计要点：
 * 1. 使用 TanStack Query 与项目其他数据获取保持一致
 * 2. 阻塞渲染直到身份校验完成
 * 3. 同步用户信息到 Zustand store 供全局访问
 * 4. 监听 token 过期事件，自动 toast 提示并重定向到登录页
 * 5. 未认证用户：local 模式重定向到 /login；sso 模式整页跳转到 giikin 单点登录入口
 */

import { type ReactNode, useEffect, useRef, useState } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Loader2 } from 'lucide-react'
import { Navigate, useLocation } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { userApi } from '@/api/user'
import {
  clearSsoAttempt,
  clearStaleGiikinSession,
  initiateSsoLogin,
  isSsoMode,
  isWithinSsoCooldown,
} from '@/config/auth'
import { useToast } from '@/hooks/use-toast'
import { useUserStore } from '@/stores/user'

const PUBLIC_PATHS = ['/login', '/register', '/sso-callback']

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: Readonly<AuthProviderProps>): React.JSX.Element {
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
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
  /** 回调页由 SsoCallbackPage 负责换票与 auth/me，避免抢先 401 触发冷却期 */
  const deferAuthMe = isOnSsoCallback

  const {
    data: currentUser,
    isLoading,
    isFetched,
    error,
    refetch,
  } = useQuery({
    queryKey: ['auth', 'currentUser'],
    queryFn: () => userApi.getCurrentUser(),
    retry: false,
    staleTime: 1000 * 60 * 5,
    enabled: !deferAuthMe,
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
      queryClient.setQueryData(['auth', 'currentUser'], null)
      void queryClient.invalidateQueries()
      void refetch()
    }
    window.addEventListener('auth:session-expired', handler)
    return () => {
      window.removeEventListener('auth:session-expired', handler)
    }
  }, [toast, queryClient, refetch])

  // 同步用户信息到 Zustand store
  useEffect(() => {
    if (isFetched) {
      setCurrentUser(sessionUser)
      if (sessionUser) {
        clearSsoAttempt()
      }
    }
  }, [sessionUser, isFetched, setCurrentUser])

  // SSO 回调后 guard_token 写入存在短延迟，冷却期内先重试 auth/me 再报错
  useEffect(() => {
    if (!isSsoMode || !isWithinSsoCooldown() || ssoPostLoginRetryDone.current || deferAuthMe) {
      return
    }
    if (!isSessionInvalid || sessionUser) {
      return
    }
    ssoPostLoginRetryDone.current = true
    setSsoPostLoginRetrying(true)
    void (async () => {
      for (let attempt = 0; attempt < 8; attempt += 1) {
        await queryClient.invalidateQueries({ queryKey: ['auth', 'currentUser'] })
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

  const isOnPublicPath = PUBLIC_PATHS.includes(location.pathname)
  const ssoCooldownActive = isWithinSsoCooldown()
  /** guard_token 为 HttpOnly，401 后须用冷却期避免 SSO 死循环 */
  const shouldStartSso =
    isSsoMode &&
    !sessionUser &&
    isFetched &&
    !isOnPublicPath &&
    isSessionInvalid &&
    !ssoCooldownActive

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

  if (isLoading && !deferAuthMe) {
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
