/** 单条模型删除确认文案（详情页 / 列表行删除共用）。 */

export type GatewayModelDeleteScope = 'personal' | 'team'

export function formatSingleGatewayModelDeleteDescription(
  displayLabel: string,
  scope: GatewayModelDeleteScope = 'team'
): string {
  if (scope === 'personal') {
    return `确定删除模型「${displayLabel}」？将同步清理相关授权与预算行。此操作不可撤销。`
  }
  return `确定删除模型「${displayLabel}」？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
}

export function resolveGatewayModelDeleteScope(
  scope: 'personal' | 'team' | 'system' | undefined
): GatewayModelDeleteScope {
  return scope === 'personal' ? 'personal' : 'team'
}
