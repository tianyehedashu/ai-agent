import { Link } from 'react-router-dom'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { personalModelsIndexHref } from '@/features/gateway-models/paths'
import type { ChatModelReadiness } from '@/types/user-model'

export function chatReadinessLabel(readiness: ChatModelReadiness | undefined): string {
  if (readiness === 'needs_credential') return '请先配置 Gateway 凭据'
  if (readiness === 'needs_model') return '请注册对话模型'
  if (readiness === 'needs_connectivity_fix') return '请修复模型连通性'
  return '暂无可用模型'
}

export function isChatReady(readiness: ChatModelReadiness | undefined): boolean {
  return readiness === 'ready'
}

/** 模型目录尚未返回时（拉取中），既非 ready 也不应展示配置告警。 */
export function isChatReadinessLoading(
  readiness: ChatModelReadiness | undefined,
  modelsLoaded: boolean
): boolean {
  return !modelsLoaded && readiness === undefined
}

interface ChatGatewaySetupAlertProps {
  readiness: ChatModelReadiness | undefined
  workspaceTeamId: string | null | undefined
  modelsLoaded: boolean
}

export function ChatGatewaySetupAlert({
  readiness,
  workspaceTeamId,
  modelsLoaded,
}: Readonly<ChatGatewaySetupAlertProps>): React.JSX.Element | null {
  if (isChatReadinessLoading(readiness, modelsLoaded)) return null
  if (isChatReady(readiness)) return null

  if (readiness === 'needs_credential') {
    return (
      <Alert variant="destructive" className="mx-auto max-w-3xl">
        <AlertTitle>无法开始对话</AlertTitle>
        <AlertDescription>
          请先在{' '}
          <Link to="/gateway/credentials" className="font-medium underline underline-offset-4">
            Gateway 凭据管理
          </Link>{' '}
          添加并启用至少一个提供商凭据。
        </AlertDescription>
      </Alert>
    )
  }

  if (readiness === 'needs_model') {
    const modelsHref = workspaceTeamId
      ? personalModelsIndexHref(workspaceTeamId)
      : '/gateway/credentials'
    return (
      <Alert variant="destructive" className="mx-auto max-w-3xl">
        <AlertTitle>凭据已就绪，还缺对话模型</AlertTitle>
        <AlertDescription>
          请前往{' '}
          <Link to={modelsHref} className="font-medium underline underline-offset-4">
            Gateway 模型管理
          </Link>{' '}
          从凭据注册至少一个 text 对话模型，或通过「添加模型」完成配置。
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <Alert variant="destructive" className="mx-auto max-w-3xl">
      <AlertTitle>模型连通性不可用</AlertTitle>
      <AlertDescription>
        已有模型但连通性测试未通过。请在 Gateway 模型详情中修复配置并重新测试，或更换其他可用模型。
      </AlertDescription>
    </Alert>
  )
}
