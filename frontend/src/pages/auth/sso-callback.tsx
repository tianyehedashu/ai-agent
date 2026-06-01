/**
 * SSO 回调页
 *
 * giikin 单点登录完成后回跳到本页：此时 guard_token Cookie 已建立，
 * 经 HiGress 注入身份。这里刷新当前用户查询并跳回原始页面。
 */

import { useEffect, useState } from 'react'

import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { AlertCircle, Loader2 } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { APP_ROOT } from '@/api/paths'
import { userApi } from '@/api/user'
import { clearSsoAttempt, markSsoAttempt, SSO_RETURN_PATH_KEY } from '@/config/auth'
import { hrefToRouterPath } from '@/lib/ui-overlay/overlay-nav-bridge'

/** React Router 路径（如 /chat）→ 浏览器 URL 路径（如 /ai-agent/chat） */
function toPublicPath(routerPath: string): string {
  const normalized = routerPath.startsWith('/') ? routerPath : `/${routerPath}`
  const root = APP_ROOT.replace(/\/$/, '')
  if (root && (normalized === root || normalized.startsWith(`${root}/`))) {
    return normalized
  }
  return root ? `${root}${normalized}` : normalized
}

function resolveReturnPath(raw: string | null): string {
  if (!raw) return '/'
  try {
    // 仅接受同源相对路径，避免开放重定向
    const url = new URL(raw, window.location.origin)
    if (url.origin !== window.location.origin) return '/'
    return url.pathname + url.search
  } catch {
    return raw.startsWith('/') ? raw : '/'
  }
}

/** plus-ui 换票后 Cookie 可能尚未就绪，短暂重试 auth/me */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

async function fetchCurrentUserWithRetry(
  queryClient: QueryClient,
  maxAttempts = 10,
  delayMs = 500
): Promise<void> {
  let lastError: unknown
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      await queryClient.invalidateQueries({ queryKey: ['auth', 'currentUser'] })
      await queryClient.fetchQuery({
        queryKey: ['auth', 'currentUser'],
        queryFn: () => userApi.getCurrentUser(),
      })
      return
    } catch (error) {
      lastError = error
      if (attempt < maxAttempts - 1) {
        await sleep(delayMs)
      }
    }
  }
  throw lastError
}

export default function SsoCallbackPage(): React.JSX.Element {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const [callbackError, setCallbackError] = useState<string | null>(null)

  useEffect(() => {
    const ticket = searchParams.get('ticket')
    // IAM 回调带 ticket：同域 plus-ui /sso-callback 完成 ticket→guard_token（登录接口需加密）
    if (ticket) {
      markSsoAttempt()
      const qs = new URLSearchParams(searchParams)
      // 换票完成后须回到本页校验 auth/me，不可直跳业务页（Cookie 写入与 auth/me 存在竞态）
      qs.set('redirect', `${window.location.origin}${toPublicPath('/sso-callback')}`)
      window.location.replace(`${window.location.origin}/sso-callback?${qs.toString()}`)
      return
    }

    const stored = sessionStorage.getItem(SSO_RETURN_PATH_KEY)
    sessionStorage.removeItem(SSO_RETURN_PATH_KEY)
    const target = resolveReturnPath(searchParams.get('redirect') ?? stored ?? `${APP_ROOT}/`)
    const navigateTarget = (() => {
      try {
        const url = new URL(target, window.location.origin)
        return hrefToRouterPath(url.pathname) + url.search
      } catch {
        const [pathname, ...rest] = target.split('?')
        const search = rest.length > 0 ? `?${rest.join('?')}` : ''
        return hrefToRouterPath(pathname) + search
      }
    })()
    void (async () => {
      try {
        await fetchCurrentUserWithRetry(queryClient)
        clearSsoAttempt()
        navigate(navigateTarget, { replace: true })
      } catch {
        markSsoAttempt()
        setCallbackError(
          '登录回调已完成，但 ai-agent 未能识别身份。请稍后重试或联系管理员检查网关配置。'
        )
      }
    })()
  }, [navigate, queryClient, searchParams])

  if (callbackError) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <p className="max-w-md text-sm text-muted-foreground">{callbackError}</p>
          <button
            type="button"
            onClick={() => {
              setCallbackError(null)
              void fetchCurrentUserWithRetry(queryClient)
                .then(() => {
                  clearSsoAttempt()
                  navigate('/', { replace: true })
                })
                .catch(() => {
                  setCallbackError(
                    '仍无法识别登录态，请确认 HiGress giikin-auth-bridge 已正确配置。'
                  )
                })
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
        <p className="text-sm text-muted-foreground">正在完成登录...</p>
      </div>
    </div>
  )
}
