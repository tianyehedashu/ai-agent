function teamBase(teamId: string): string {
  return `/gateway/teams/${encodeURIComponent(teamId)}`
}

export type ModelScopeParam = 'personal' | 'team' | 'system'

/** @deprecated 详情深链仍可读 legacy tab；新链接请用 scope */
export type TeamModelsTab = 'shared' | 'system'

type LegacyModelsDetailTab = 'shared' | 'system'

function modelsListBaseParams(
  options?: Readonly<{ credentialId?: string; scope?: ModelScopeParam }>
): URLSearchParams {
  const params = new URLSearchParams()
  if (options?.credentialId) {
    params.set('credentialId', options.credentialId)
  }
  if (options?.scope) {
    params.set('scope', options.scope)
  }
  return params
}

function modelsRegisterBaseParams(scope: ModelScopeParam, credentialId?: string): URLSearchParams {
  const params = modelsListBaseParams({ scope, credentialId })
  params.set('view', 'register')
  return params
}

/** 模型统一列表 */
export function modelsIndexHref(
  teamId: string,
  options?: Readonly<{ credentialId?: string; scope?: ModelScopeParam }>
): string {
  const qs = modelsListBaseParams(options).toString()
  return `${teamBase(teamId)}/models${qs ? `?${qs}` : ''}`
}

/** 个人模型列表（统一页） */
export function personalModelsIndexHref(teamId: string): string {
  return modelsIndexHref(teamId)
}

/** 个人模型注册（可选锁定凭据） */
export function personalModelsRegisterHref(teamId: string, credentialId?: string): string {
  return `${teamBase(teamId)}/models?${modelsRegisterBaseParams('personal', credentialId).toString()}`
}

function legacyPersonalDetailParams(): URLSearchParams {
  return new URLSearchParams({ tab: 'personal' })
}

/** 个人模型详情深链 */
export function personalModelDetailHref(teamId: string, modelId: string): string {
  return `${teamBase(teamId)}/models/${encodeURIComponent(modelId)}?${legacyPersonalDetailParams().toString()}`
}

/** @deprecated 编辑已并入详情页；保留兼容旧链接 */
export function personalModelEditHref(teamId: string, modelId: string): string {
  return personalModelDetailHref(teamId, modelId)
}

function legacyTeamDetailParams(
  credentialId?: string,
  tab: LegacyModelsDetailTab = 'shared'
): URLSearchParams {
  const params = new URLSearchParams({ tab })
  if (credentialId) {
    params.set('credentialId', credentialId)
  }
  return params
}

/** 团队模型列表（可选按凭据筛选；统一页） */
export function teamModelsFilteredHref(teamId: string, credentialId?: string): string {
  return modelsIndexHref(teamId, { credentialId, scope: credentialId ? 'team' : undefined })
}

/** @deprecated 与统一列表同 URL */
export function systemModelsBrowseIndexHref(teamId: string): string {
  return modelsIndexHref(teamId)
}

/** 系统模型列表深链（统一页；可选按凭据筛选） */
export function systemModelsFilteredHref(teamId: string, credentialId?: string): string {
  return modelsIndexHref(teamId, { credentialId, scope: credentialId ? 'system' : undefined })
}

/** 团队模型注册（可选锁定凭据） */
export function teamModelsRegisterHref(
  teamId: string,
  credentialId?: string,
  tab: LegacyModelsDetailTab = 'shared'
): string {
  const scope: ModelScopeParam = tab === 'system' ? 'system' : 'team'
  return `${teamBase(teamId)}/models?${modelsRegisterBaseParams(scope, credentialId).toString()}`
}

/** 团队注册模型详情深链（可选凭据上下文与 legacy tab） */
export function teamModelDetailHref(
  teamId: string,
  modelId: string,
  options?: { credentialId?: string; tab?: LegacyModelsDetailTab }
): string {
  return `${teamBase(teamId)}/models/${encodeURIComponent(modelId)}?${legacyTeamDetailParams(options?.credentialId, options?.tab ?? 'shared').toString()}`
}

/** 系统模型详情深链（平台管理员） */
export function systemModelDetailHref(
  teamId: string,
  modelId: string,
  credentialId?: string
): string {
  return teamModelDetailHref(teamId, modelId, { credentialId, tab: 'system' })
}

/** 团队模型列表首页 */
export function teamModelsIndexHref(teamId: string): string {
  return modelsIndexHref(teamId)
}

export type CredentialsListTab = 'personal' | 'shared' | 'system'

function credentialsBaseParams(
  options?: Readonly<{ credentialId?: string; view?: 'create' | 'edit' }>
): URLSearchParams {
  const params = new URLSearchParams()
  if (options?.credentialId) {
    params.set('credentialId', options.credentialId)
  }
  if (options?.view) {
    params.set('view', options.view)
  }
  return params
}

/** 个人凭据深链（统一列表页，可选定位凭据） */
export function personalCredentialsIndexHref(
  teamId: string,
  options?: Readonly<{ credentialId?: string; view?: 'create' | 'edit' }>
): string {
  return credentialsListHref(teamId, options)
}

/** 凭据列表（统一页；legacy tab 参数已不再写入 URL） */
export function credentialsListHref(
  teamId: string,
  options?: Readonly<{ credentialId?: string; view?: 'create' | 'edit' }>
): string {
  const qs = credentialsBaseParams(options).toString()
  return `${teamBase(teamId)}/credentials${qs ? `?${qs}` : ''}`
}

/** @deprecated 与统一列表同 URL；保留别名供旧链接兼容 */
export function credentialsTeamListHref(
  teamId: string,
  options?: Readonly<{ credentialId?: string }>
): string {
  return credentialsListHref(teamId, options)
}

/** @deprecated 与统一列表同 URL；保留别名供旧链接兼容 */
export function credentialsSystemBrowseIndexHref(
  teamId: string,
  options?: Readonly<{ credentialId?: string }>
): string {
  return credentialsListHref(teamId, options)
}

/** 凭据详情（可选带来源 Tab） */
export function credentialDetailHref(
  teamId: string,
  credentialId: string,
  options?: Readonly<{ tab?: CredentialsListTab }>
): string {
  const path = `${teamBase(teamId)}/credentials/${encodeURIComponent(credentialId)}`
  if (options?.tab) {
    return `${path}?tab=${options.tab}`
  }
  return path
}

/** 凭据详情并打开「添加模型」弹窗（由详情页根据 query 派生展示，无需 effect） */
export function credentialDetailAddModelsHref(teamId: string, credentialId: string): string {
  return `${credentialDetailHref(teamId, credentialId)}?addModels=1`
}
