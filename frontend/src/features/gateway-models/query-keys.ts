/** 凭据关联模型列表 query key（读侧含 teamId + tab；失效时可省略 tab 前缀匹配） */
export function gatewayModelsByCredentialQueryKey(
  teamId: string,
  credentialId: string,
  modelsTab: 'shared' | 'system' = 'shared'
): readonly ['gateway', 'models', string, 'by-credential', string, 'shared' | 'system'] {
  return ['gateway', 'models', teamId, 'by-credential', credentialId, modelsTab]
}

/** 失效某凭据下全部 tab 的关联模型缓存（可选限定 teamId） */
export function gatewayModelsByCredentialInvalidatePrefix(
  credentialId: string,
  teamId?: string
): readonly string[] {
  if (teamId) {
    return ['gateway', 'models', teamId, 'by-credential', credentialId]
  }
  return ['gateway', 'models', 'by-credential', credentialId]
}
