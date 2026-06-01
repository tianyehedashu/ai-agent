/**
 * 上游 model id 客户端兜底推断（仅当 probe API **未**返回 ``inferred_model_types`` 时使用）。
 *
 * SSOT：backend ``upstream_type_inference.infer_upstream_model_types`` +
 * ``infer_upstream_model_types_for_catalog``（含 LiteLLM hint）。
 * 凭据探测 / 批量导入应优先使用 ``resolveUpstreamModelTypes`` 的服务端字段。
 */

import type { ModelType } from '@/types/user-model'

const VALID_TYPES: readonly ModelType[] = ['text', 'image', 'image_gen', 'video']

const NON_IMPORTABLE = /embedding|embed|rerank|moderation|whisper|tts|speech|transcri/i

/** 无服务端推断时的保守兜底：不可导入 SKU 为空，其余视为纯文本。 */
export function inferUpstreamModelTypes(
  _provider: string,
  upstreamId: string,
  ownedBy?: string | null
): ModelType[] {
  const mid = upstreamId.trim()
  if (!mid) return []

  const haystack = ownedBy ? `${mid} ${ownedBy}` : mid
  if (NON_IMPORTABLE.test(haystack)) return []

  return ['text']
}

export function resolveUpstreamModelTypes(
  item: { id: string; owned_by?: string | null; inferred_model_types?: string[] },
  provider: string
): ModelType[] {
  const fromServer = item.inferred_model_types
  if (fromServer !== undefined && fromServer.length > 0) {
    return fromServer.filter((t): t is ModelType => (VALID_TYPES as readonly string[]).includes(t))
  }
  if (fromServer?.length === 0) {
    return []
  }
  return inferUpstreamModelTypes(provider, item.id, item.owned_by)
}
