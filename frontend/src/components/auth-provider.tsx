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
 * 4. 监听 token 过期事件，自动 toast 提示并切换到匿名身份
 */

import { type ReactNode, useEffect } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Loader2 } from 'lucide-react'

import { ApiError } from '@/api/client'
import { userApi } from '@/api/user'
import { useToast } from '@/hooks/use-toast'
import { useUserStore } from '@/stores/user'

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: Readonly<AuthProviderProps>): React.JSX.Element {
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const queryClient = useQueryClient()
  const { toast } = useToast()

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

  // 监听 token 过期事件（由 apiClient 在 401 + 有旧 token 时发出）
  useEffect(() => {
    const handler = (): void => {
      toast({
        variant: 'destructive',
        title: '登录已过期',
        description: '请重新登录以恢复数据访问',
      })
      void queryClient.invalidateQueries()
      void refetch()
    }
    window.addEventListener('auth:session-expired', handler)
    return () => { window.removeEventListener('auth:session-expired', handler) }
  }, [toast, queryClient, refetch])

  // 同步用户信息到 Zustand store
  useEffect(() => {
    if (isFetched) {
      setCurrentUser(currentUser ?? null)
    }
  }, [currentUser, isFetched, setCurrentUser])

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

  // 严重错误状态（如服务不可用）- 401/403 是正常的未登录状态
  const isAuthError = error instanceof ApiError && (error.status === 401 || error.status === 403)
  if (error && !isAuthError) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <div>
            <p className="font-medium text-foreground">连接失败</p>
            <p className="mt-1 text-sm text-muted-foreground">无法连接到服务器，请检查网络连接</p>
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

  return <>{children}</>
}
