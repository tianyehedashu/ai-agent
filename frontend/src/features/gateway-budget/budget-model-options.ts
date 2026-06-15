import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'
import type { GatewayRoute } from '@/api/gateway/routes'

export interface BudgetModelOption {
  name: string
  group: 'registry' | 'route' | 'legacy'
  provider?: string
  capability?: string
  registryKind?: 'team' | 'system'
  enabled?: boolean
}

const GROUP_ORDER: Record<BudgetModelOption['group'], number> = {
  registry: 0,
  route: 1,
  legacy: 2,
}

function sortOptions(a: BudgetModelOption, b: BudgetModelOption): number {
  const groupDiff = GROUP_ORDER[a.group] - GROUP_ORDER[b.group]
  if (groupDiff !== 0) return groupDiff
  return a.name.localeCompare(b.name)
}

export function buildBudgetModelOptions(input: {
  models: readonly GatewayModel[]
  routes: readonly GatewayRoute[]
  existingModelNames: readonly (string | null | undefined)[]
}): BudgetModelOption[] {
  const seenNames = new Set<string>()
  const options: BudgetModelOption[] = []

  for (const model of input.models) {
    const name = model.name.trim()
    if (!name || seenNames.has(name)) continue
    seenNames.add(name)
    options.push({
      name,
      group: 'registry',
      provider: model.provider,
      capability: model.capability,
      registryKind: model.registry_kind,
      enabled: model.enabled,
    })
  }

  for (const route of input.routes) {
    const name = route.virtual_model.trim()
    if (!name || seenNames.has(name)) continue
    seenNames.add(name)
    options.push({
      name,
      group: 'route',
      enabled: route.enabled,
    })
  }

  const knownNames = seenNames
  const legacyNames = new Set<string>()
  for (const raw of input.existingModelNames) {
    const name = (raw ?? '').trim()
    if (!name || knownNames.has(name) || legacyNames.has(name)) continue
    legacyNames.add(name)
    options.push({
      name,
      group: 'legacy',
    })
  }

  return [...options].sort(sortOptions)
}

/** 上游配额：按所选凭据过滤，选项值为 upstream real_model（非 Gateway 别名）。 */
export function buildUpstreamQuotaModelOptions(input: {
  models?: readonly GatewayModel[]
  personalModels?: readonly PersonalGatewayModel[]
  credentialIds: readonly string[]
  existingModelNames: readonly (string | null | undefined)[]
}): BudgetModelOption[] {
  const credSet = new Set(input.credentialIds)
  const seenReal = new Set<string>()
  const options: BudgetModelOption[] = []

  for (const model of input.models ?? []) {
    if (!credSet.has(model.credential_id)) continue
    const realModel = model.real_model.trim()
    if (!realModel || seenReal.has(realModel)) continue
    seenReal.add(realModel)
    options.push({
      name: realModel,
      group: 'registry',
      provider: model.provider,
      capability: model.capability,
      registryKind: model.registry_kind,
      enabled: model.enabled,
    })
  }

  for (const model of input.personalModels ?? []) {
    if (!credSet.has(model.credential_id)) continue
    const realModel = model.model_id.trim()
    if (!realModel || seenReal.has(realModel)) continue
    seenReal.add(realModel)
    options.push({
      name: realModel,
      group: 'registry',
      provider: model.provider,
      capability: model.capability,
      enabled: model.is_active,
    })
  }

  for (const raw of input.existingModelNames) {
    const name = (raw ?? '').trim()
    if (!name || seenReal.has(name)) continue
    let onSelectedCred = false
    for (const model of input.models ?? []) {
      if (credSet.has(model.credential_id) && model.real_model.trim() === name) {
        onSelectedCred = true
        break
      }
    }
    if (!onSelectedCred) {
      for (const model of input.personalModels ?? []) {
        if (credSet.has(model.credential_id) && model.model_id.trim() === name) {
          onSelectedCred = true
          break
        }
      }
    }
    if (!onSelectedCred) continue
    seenReal.add(name)
    options.push({
      name,
      group: 'legacy',
    })
  }

  return [...options].sort(sortOptions)
}

export function upstreamQuotaModelOptionLabel(
  option: BudgetModelOption,
  aliasByRealModel?: ReadonlyMap<string, string>
): string {
  if (option.group === 'legacy') return '历史配置'
  const alias = aliasByRealModel?.get(option.name)
  const base = budgetModelOptionLabel(option)
  return alias
    ? `${option.name} · ${alias}`
    : base === '注册模型'
      ? option.name
      : `${option.name} · ${base}`
}

export function budgetModelOptionLabel(option: BudgetModelOption): string {
  if (option.group === 'route') return '虚拟路由'
  if (option.group === 'legacy') return '历史配置'
  const parts: string[] = []
  if (option.provider) parts.push(option.provider)
  if (option.capability) parts.push(option.capability)
  if (option.registryKind === 'system') parts.push('系统')
  if (option.enabled === false) parts.push('已禁用')
  return parts.length > 0 ? parts.join(' · ') : '注册模型'
}

export const BUDGET_MODEL_GROUP_LABELS: Record<BudgetModelOption['group'], string> = {
  registry: '注册模型',
  route: '虚拟路由',
  legacy: '历史配置',
}

export const BUDGET_MODEL_GROUP_ORDER: readonly BudgetModelOption['group'][] = [
  'registry',
  'route',
  'legacy',
]

export function groupBudgetModelOptions(
  options: readonly BudgetModelOption[]
): Record<BudgetModelOption['group'], BudgetModelOption[]> {
  const groups: Record<BudgetModelOption['group'], BudgetModelOption[]> = {
    registry: [],
    route: [],
    legacy: [],
  }
  for (const option of options) {
    groups[option.group].push(option)
  }
  return groups
}

export function budgetModelOptionsByName(
  options: readonly BudgetModelOption[]
): ReadonlyMap<string, BudgetModelOption> {
  return new Map(options.map((option) => [option.name, option]))
}
