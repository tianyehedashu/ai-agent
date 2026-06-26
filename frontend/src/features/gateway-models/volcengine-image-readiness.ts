/**
 * 火山 Seedream 生图：凭据 extra.image_endpoint_id 是否就绪（与后端 parse 规则对齐）。
 */

export function parseVolcengineImageEndpointId(
  extra: Record<string, unknown> | null | undefined
): string | null {
  const raw = extra?.image_endpoint_id
  if (typeof raw !== 'string') return null
  const trimmed = raw.trim()
  return trimmed.length > 0 ? trimmed : null
}

export function needsVolcengineImageEndpointSetup(
  provider: string,
  capability: string,
  extra: Record<string, unknown> | null | undefined
): boolean {
  if (provider.trim().toLowerCase() !== 'volcengine') return false
  if (capability.trim().toLowerCase() !== 'image') return false
  return parseVolcengineImageEndpointId(extra) === null
}

export const VOLCENGINE_IMAGE_ENDPOINT_HINT =
  '火山文生图须在绑定凭据的 extra 中配置生图接入点 image_endpoint_id（ep-m-xxx，与 API Key 同账号）。保存后可到「凭据」页补充，再执行连通性测试。'
