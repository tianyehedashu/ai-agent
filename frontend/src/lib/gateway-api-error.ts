import { ApiError } from '@/api/errors'

/** 将 Gateway 管理 API 错误转为用户可读文案（试调 Key reveal 等）。 */
export function formatGatewayManagementError(error: Error): string {
  if (!(error instanceof ApiError)) {
    return error.message
  }
  const raw = error.message.trim()
  if (error.status === 404 && (raw === 'Not Found' || raw === 'Not found')) {
    return '接口不存在（404）。请确认后端已更新并重启；若 Key 已撤销或属于其他团队，请重新选择。'
  }
  if (error.status === 403) {
    return raw.length > 0 ? raw : '无权访问该资源（403）'
  }
  return raw.length > 0 ? raw : `请求失败（${String(error.status)}）`
}
