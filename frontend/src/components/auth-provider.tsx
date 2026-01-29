/**
 * Auth Provider
 *
 * 确保在应用初始化时先完成身份验证调用，
 * 等待匿名用户 Cookie 设置完成后再渲染子组件。
 *
 * 这解决了多个并行请求在 Cookie 建立之前同时发出，
 * 导致生成多个不同匿名用户 ID 的竞态条件问题。
 *
 * 设计要点：
 * 1. 使用 TanStack Query 与项目其他数据获取保持一致
 * 2. 阻塞渲染直到 Cookie 建立完成
 * 3. 同步用户信息到 Zustand store 供全局访问
 */

import { type ReactNode, useEffect } from 'react'

import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Loader2 } from 'lucide-react'

import { userApi } from '@/api/user'
import { useUserStore } from '@/stores/user'

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: Readonly<AuthProviderProps>): React.JSX.Element {
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)

  // 使用 TanStack Query 获取当前用户信息
  // 这会确保 Cookie 在后续请求之前被设置
  const { data: currentUser, isLoading, isFetched, error, refetch } = useQuery({
    queryKey: ['auth', 'currentUser'],
    queryFn: () => userApi.getCurrentUser(),
    retry: false, // 不重试，失败说明未登录或服务不可用
    staleTime: 1000 * 60 * 5, // 5 分钟内不重新获取
  })

  // 同步用户信息到 Zustand store
  useEffect(() => {
    if (isFetched) {
      setCurrentUser(currentUser ?? null)
    }
  }, [currentUser, isFetched, setCurrentUser])

  // 加载状态
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

  // 严重错误状态（如服务不可用）- 仅在非 401/403 时显示
  // 401/403 是正常的未认证状态，不需要显示错误
  if (error && !error.message.includes('401') && !error.message.includes('403')) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <div>
            <p className="font-medium text-foreground">连接失败</p>
            <p className="mt-1 text-sm text-muted-foreground">
              无法连接到服务器，请检查网络连接
            </p>
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
