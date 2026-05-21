function teamBase(teamId: string): string {
  return `/gateway/teams/${encodeURIComponent(teamId)}`
}

function personalModelsBaseParams(): URLSearchParams {
  return new URLSearchParams({ tab: 'personal' })
}

/** 个人模型列表 */
export function personalModelsIndexHref(teamId: string): string {
  return `${teamBase(teamId)}/models?${personalModelsBaseParams().toString()}`
}

/** 个人模型注册 */
export function personalModelsRegisterHref(teamId: string): string {
  const params = personalModelsBaseParams()
  params.set('view', 'register')
  return `${teamBase(teamId)}/models?${params.toString()}`
}

/** 个人模型详情深链 */
export function personalModelDetailHref(teamId: string, modelId: string): string {
  const params = personalModelsBaseParams()
  return `${teamBase(teamId)}/models/${encodeURIComponent(modelId)}?${params.toString()}`
}

/** 个人模型编辑（详情页子视图） */
export function personalModelEditHref(teamId: string, modelId: string): string {
  const params = personalModelsBaseParams()
  params.set('view', 'edit')
  return `${teamBase(teamId)}/models/${encodeURIComponent(modelId)}?${params.toString()}`
}

function teamModelsBaseParams(credentialId?: string): URLSearchParams {
  const params = new URLSearchParams({ tab: 'shared' })
  if (credentialId) {
    params.set('credentialId', credentialId)
  }
  return params
}

/** 团队模型列表（可选按凭据筛选） */
export function teamModelsFilteredHref(teamId: string, credentialId?: string): string {
  return `${teamBase(teamId)}/models?${teamModelsBaseParams(credentialId).toString()}`
}

function systemModelsBaseParams(credentialId?: string): URLSearchParams {
  const params = new URLSearchParams({ tab: 'system' })
  if (credentialId) {
    params.set('credentialId', credentialId)
  }
  return params
}

/** 系统模型列表（平台管理员；可选按凭据筛选） */
export function systemModelsFilteredHref(teamId: string, credentialId?: string): string {
  return `${teamBase(teamId)}/models?${systemModelsBaseParams(credentialId).toString()}`
}

/** 团队模型注册（可选锁定凭据） */
export function teamModelsRegisterHref(teamId: string, credentialId?: string): string {
  const params = teamModelsBaseParams(credentialId)
  params.set('view', 'register')
  return `${teamBase(teamId)}/models?${params.toString()}`
}

/** 团队注册模型详情深链（可选凭据上下文） */
export function teamModelDetailHref(
  teamId: string,
  modelId: string,
  options?: { credentialId?: string }
): string {
  const params = teamModelsBaseParams(options?.credentialId)
  return `${teamBase(teamId)}/models/${encodeURIComponent(modelId)}?${params.toString()}`
}

/** 团队模型列表首页 */
export function teamModelsIndexHref(teamId: string): string {
  return teamModelsFilteredHref(teamId)
}

/** 凭据管理（团队 Tab；URL 字面量与后端 `Team.kind='shared'` 对齐） */
export function credentialsTeamListHref(teamId: string): string {
  return `${teamBase(teamId)}/credentials?tab=shared`
}

/** 凭据详情 */
export function credentialDetailHref(teamId: string, credentialId: string): string {
  return `${teamBase(teamId)}/credentials/${encodeURIComponent(credentialId)}`
}

/** 凭据详情并打开「添加模型」弹窗（由详情页根据 query 派生展示，无需 effect） */
export function credentialDetailAddModelsHref(teamId: string, credentialId: string): string {
  return `${credentialDetailHref(teamId, credentialId)}?addModels=1`
}
