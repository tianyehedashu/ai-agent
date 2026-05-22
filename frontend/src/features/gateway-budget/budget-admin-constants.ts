import type { GatewayBudget } from '@/api/gateway/budgets'

export type BudgetAdminTab = GatewayBudget['target_kind']

export const TAB_LABELS: Record<BudgetAdminTab, string> = {
  tenant: '团队',
  user: '用户',
  key: '虚拟 Key',
  system: '系统',
}

export function parseAdminTab(raw: string | null, showSystem: boolean): BudgetAdminTab {
  if (raw === 'user' || raw === 'key' || raw === 'system') {
    if (raw === 'system' && !showSystem) return 'tenant'
    return raw
  }
  return 'tenant'
}

export function adminTabsForPlatform(isPlatformAdmin: boolean): BudgetAdminTab[] {
  return isPlatformAdmin ? ['tenant', 'user', 'key', 'system'] : ['tenant', 'user', 'key']
}
