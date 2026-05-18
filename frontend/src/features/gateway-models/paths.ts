function personalModelsBaseParams(): URLSearchParams {
  return new URLSearchParams({ tab: 'personal' })
}

/** 个人模型列表 */
export function personalModelsIndexHref(): string {
  return `/gateway/models?${personalModelsBaseParams().toString()}`
}

/** 个人模型注册 */
export function personalModelsRegisterHref(): string {
  const params = personalModelsBaseParams()
  params.set('view', 'register')
  return `/gateway/models?${params.toString()}`
}

/** 个人模型详情深链 */
export function personalModelDetailHref(modelId: string): string {
  const params = personalModelsBaseParams()
  return `/gateway/models/${encodeURIComponent(modelId)}?${params.toString()}`
}

/** 个人模型编辑（详情页子视图） */
export function personalModelEditHref(modelId: string): string {
  const params = personalModelsBaseParams()
  params.set('view', 'edit')
  return `/gateway/models/${encodeURIComponent(modelId)}?${params.toString()}`
}

function teamModelsBaseParams(credentialId?: string): URLSearchParams {
  const params = new URLSearchParams({ tab: 'team' })
  if (credentialId) {
    params.set('credentialId', credentialId)
  }
  return params
}

/** 团队模型列表（可选按凭据筛选） */
export function teamModelsFilteredHref(credentialId?: string): string {
  return `/gateway/models?${teamModelsBaseParams(credentialId).toString()}`
}

/** 团队模型注册（可选锁定凭据） */
export function teamModelsRegisterHref(credentialId?: string): string {
  const params = teamModelsBaseParams(credentialId)
  params.set('view', 'register')
  return `/gateway/models?${params.toString()}`
}

/** 团队注册模型详情深链（可选凭据上下文） */
export function teamModelDetailHref(modelId: string, options?: { credentialId?: string }): string {
  const params = teamModelsBaseParams(options?.credentialId)
  return `/gateway/models/${encodeURIComponent(modelId)}?${params.toString()}`
}

/** 团队模型列表首页 */
export function teamModelsIndexHref(): string {
  return teamModelsFilteredHref()
}

/** 凭据管理（团队 Tab） */
export function credentialsTeamListHref(): string {
  return '/gateway/credentials?tab=team'
}

/** 凭据详情 */
export function credentialDetailHref(credentialId: string): string {
  return `/gateway/credentials/${encodeURIComponent(credentialId)}`
}
