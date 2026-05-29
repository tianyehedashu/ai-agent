import { ApiError } from '@/api/errors'

function isGenericNotFoundMessage(message: string): boolean {
  const raw = message.trim()
  return raw === 'Not Found' || raw === 'Not found'
}

/** 团队不存在 / 无权访问（404 TEAM_NOT_FOUND 或文案含「团队不存在」）。 */
export function isGatewayTeamAccessError(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false
  if (error.code === 'TEAM_NOT_FOUND') return true
  if (error.status !== 404) return false
  const raw = error.message.trim()
  return raw.includes('团队不存在')
}

/** Gateway 列表/大盘等 React Query 错误的用户可读文案。 */
export function formatGatewayQueryError(error: unknown, fallback = '加载失败'): string {
  if (!(error instanceof ApiError)) {
    return error instanceof Error && error.message.trim().length > 0 ? error.message : fallback
  }
  if (isGatewayTeamAccessError(error)) {
    return error.message.trim().length > 0
      ? error.message
      : '工作区不存在或无权访问，请从侧栏重新选择团队'
  }
  const raw = error.message.trim()
  if (error.status === 404 && isGenericNotFoundMessage(raw)) {
    return '接口不存在（404）。请确认后端已更新并重启。'
  }
  if (error.status === 403) {
    return raw.length > 0 ? raw : '无权访问该资源（403）'
  }
  return raw.length > 0 ? raw : `${fallback}（${String(error.status)}）`
}

/** 将 Gateway 管理 API 错误转为用户可读文案（试调 Key reveal 等）。 */
export function formatGatewayManagementError(error: Error): string {
  if (!(error instanceof ApiError)) {
    return error.message
  }
  return formatGatewayQueryError(error, '请求失败')
}
