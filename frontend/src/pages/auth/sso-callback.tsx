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
    // IAM 回调带 ticket 时：同域 plus-ui /sso-callback 完成 ticket→guard_token（IAM 登录接口需加密）
    if (ticket) {
      const qs = searchParams.toString()
      window.location.replace(`${window.location.origin}/sso-callback?${qs}`)
      return
    }

    const stored = sessionStorage.getItem(SSO_RETURN_PATH_KEY)
    sessionStorage.removeItem(SSO_RETURN_PATH_KEY)
    const target = resolveReturnPath(searchParams.get('redirect') ?? stored ?? `${APP_ROOT}/`)
    void queryClient.invalidateQueries({ queryKey: ['auth', 'currentUser'] }).then(() => {
      navigate(target, { replace: true })
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
