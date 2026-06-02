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
import {
  clearSsoAttempt,
  clearStaleGiikinSession,
  consumeSsoReturnPath,
  getSsoAttemptCount,
  initiateSsoLogin,
  markSsoAttempt,
  SSO_MAX_ATTEMPTS,
} from '@/config/auth'
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
  const [autoRecovering, setAutoRecovering] = useState(false)

  useEffect(() => {
    const ticket = searchParams.get('ticket')
    // IAM 回调带 ticket：调用 ai-agent 后端 sso-exchange 换票，
    // 由后端将 guard_token Cookie 以无 Domain 方式设置到 gateway.giimallai.com
    // （HiGress 未透传 IAM 的 Set-Cookie 导致 Domain=.giikin.com 在 giimallai.com 下不可用）
    if (ticket) {
      markSsoAttempt()
      const exchangeTicket = async (): Promise<void> => {
        try {
          const resp = await fetch(`${APP_ROOT}/api/v1/auth/sso-exchange`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticket }),
          })
          if (!resp.ok) {
            throw new Error(`SSO 换票失败 (${String(resp.status)})`)
          }
          // 换票成功：guard_token Cookie 已落网关域，重新加载本页校验 auth/me
          window.location.replace(`${window.location.origin}${toPublicPath('/sso-callback')}`)
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : 'SSO 换票异常'
          setCallbackError(message)
        }
      }
      void exchangeTicket()
      return
    }

    // 优先 sessionStorage，降级到 cookie（无痕模式下 sessionStorage 可能被清理）
    const stored = consumeSsoReturnPath()
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
        console.warn('[SSO] callback: auth/me succeeded, navigating to', navigateTarget)
        navigate(navigateTarget, { replace: true })
      } catch {
        const attemptCount = getSsoAttemptCount()
        console.warn(
          `[SSO] callback: fetchCurrentUserWithRetry failed, attemptCount=${String(attemptCount)}/${String(SSO_MAX_ATTEMPTS)}`
        )
        if (attemptCount >= SSO_MAX_ATTEMPTS) {
          clearSsoAttempt()
          setCallbackError(
            `连续 ${String(SSO_MAX_ATTEMPTS)} 次 SSO 登录后仍无法获取身份，可能原因：guard_token Cookie 未正确设置。请联系管理员检查 HiGress giikin-auth-bridge 配置。`
          )
          return
        }
        // 与 AuthProvider 对称：先清 stale Cookie，再自动重新发起 SSO；失败才落到手动重试页
        setAutoRecovering(true)
        await clearStaleGiikinSession()
        // 注意：此处不清除 clearSsoAttempt()，因为 initiateSsoLogin 内部会 markSsoAttempt()
        // 保持尝试计数器不被重置，以便断路器生效
        try {
          await initiateSsoLogin(target)
        } catch (err: unknown) {
          setAutoRecovering(false)
          const message = err instanceof Error ? err.message : 'SSO 登录初始化失败'
          setCallbackError(`登录凭证已失效且自动重新登录失败：${message}`)
        }
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
              setAutoRecovering(true)
              void (async () => {
                await clearStaleGiikinSession()
                clearSsoAttempt()
                try {
                  await initiateSsoLogin('/')
                } catch (err: unknown) {
                  setAutoRecovering(false)
                  const message = err instanceof Error ? err.message : 'SSO 登录初始化失败'
                  setCallbackError(`仍无法重新登录：${message}`)
                }
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

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          {autoRecovering ? '登录已过期，正在重新登录…' : '正在完成登录...'}
        </p>
      </div>
    </div>
  )
}
