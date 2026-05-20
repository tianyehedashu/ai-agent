/**
 * Gateway PII 守卫展示文案（全局开关由 GET /api/v1/gateway/features 提供）。
 */

export function guardrailStatusLabel(guardrailEnabled: boolean, globallyEnabled: boolean): string {
  if (!globallyEnabled) {
    return '未开放'
  }
  return guardrailEnabled ? '已启用' : '关闭'
}
