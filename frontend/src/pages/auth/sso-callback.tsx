/**
 * SSO 回调页
 *
 * giikin 单点登录完成后回跳到本页：此时 guard_token Cookie 已建立，
 * 经 HiGress 注入身份。这里刷新当前用户查询并跳回原始页面。
 */

import { useEffect } from 'react'

import { useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { APP_ROOT } from '@/api/paths'
import { SSO_RETURN_PATH_KEY } from '@/config/auth'
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

export default function SsoCallbackPage(): React.JSX.Element {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    const ticket = searchParams.get('ticket')
    // IAM 回调带 ticket：同域 plus-ui /sso-callback 完成 ticket→guard_token（登录接口需加密）
    if (ticket) {
      const qs = new URLSearchParams(searchParams)
      const stored = sessionStorage.getItem(SSO_RETURN_PATH_KEY)
      const returnPath = stored?.startsWith('/') ? stored : '/'
      qs.set('redirect', `${window.location.origin}${toPublicPath(returnPath)}`)
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
    void queryClient.invalidateQueries({ queryKey: ['auth', 'currentUser'] }).then(() => {
      navigate(navigateTarget, { replace: true })
    })
  }, [navigate, queryClient, searchParams])

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">正在完成登录...</p>
      </div>
    </div>
  )
}
