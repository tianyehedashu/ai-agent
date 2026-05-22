/**
 * Auth Provider
 *
 * 确保在应用初始化时先完成身份验证调用，
 * 等待匿名用户 Cookie 设置完成后再渲染子组件。
 *
 * 设计要点：
 * 1. 使用 TanStack Query 与项目其他数据获取保持一致
 * 2. 阻塞渲染直到 Cookie 建立完成
 * 3. 同步用户信息到 Zustand store 供全局访问
 * 4. 监听 token 过期事件，自动 toast 提示并重定向到登录页
 * 5. 未认证用户自动重定向到 /login（公开路由除外）
 */

import { type ReactNode, useEffect } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Loader2 } from 'lucide-react'
import { Navigate, useLocation } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { userApi } from '@/api/user'
import { useToast } from '@/hooks/use-toast'
import { useUserStore } from '@/stores/user'

const PUBLIC_PATHS = ['/login', '/register']

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: Readonly<AuthProviderProps>): React.JSX.Element {
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const location = useLocation()

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
    }
  }, [sessionUser, isFetched, setCurrentUser])

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">正在加载...</p>
        </div>
      </div>
    )
  }

  const isOnPublicPath = PUBLIC_PATHS.includes(location.pathname)

  // 严重错误状态（如服务不可用）- auth/me 的 401 走下方登录重定向
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

  // 未认证 + 不在公开页面 → 重定向到登录页（保留原始路径以便登录后跳回）
  if (!sessionUser && isFetched && !isOnPublicPath) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  return <>{children}</>
}
