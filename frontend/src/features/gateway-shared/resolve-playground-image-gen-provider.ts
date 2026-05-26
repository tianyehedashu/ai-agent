/**
 * Playground 生图：推断用于尺寸预设的 provider。
 * 凭据筛选仅缩小列表，真正路由以所选模型的 ``provider`` 为准。
 */

/** 火山方舟 image/chat endpoint 常以 ``ep-`` 开头 */
export function inferImageGenProviderFromModelName(
  modelName: string | undefined
): string | undefined {
  const name = modelName?.trim().toLowerCase()
  if (!name) return undefined
  if (name.startsWith('ep-')) return 'volcengine'
  return undefined
}

export function resolvePlaygroundImageGenProvider(
  credentialProvider: string | undefined,
  modelProvider: string | undefined,
  modelName?: string
): string | undefined {
  const fromModel = modelProvider?.trim()
  if (fromModel) return fromModel
  const fromCredential = credentialProvider?.trim()
  if (fromCredential) return fromCredential
  return inferImageGenProviderFromModelName(modelName)
}
