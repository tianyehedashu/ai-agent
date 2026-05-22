/**
 * 上游 model id → personal model_types（与 backend upstream_type_inference 对齐）。
 * 仅在后端未返回 inferred_model_types 时作兜底。
 */

import type { ModelType } from '@/types/user-model'

const VALID_TYPES: readonly ModelType[] = ['text', 'image', 'image_gen', 'video']

const NON_IMPORTABLE = /embedding|embed|rerank|moderation|whisper|tts|speech|transcri/i

const IMAGE_GEN =
  /(^dall-e|dall-e|\/dall-e|imagen|flux|stable-diffusion|sdxl|wanx.*image|wan.*-image|gpt-image|image-1|\/image\/)/i

const VIDEO =
  /(^sora|\/sora|sora-|wan.*t2v|wanx.*video|cogvideox|kling|runway|luma|veo|seedance|video-gen|\/video\/)/i

const VISION_CHAT =
  /(-vl-|\/vl\/|vision|omni|gpt-4o|gpt-4\.1|gpt-5|claude-3|claude-sonnet|claude-opus|claude-haiku|gemini-|qwen.*vl|qwen-vl|glm-4v|yi-vision)/i

export function inferUpstreamModelTypes(
  _provider: string,
  upstreamId: string,
  ownedBy?: string | null
): ModelType[] {
  const mid = upstreamId.trim()
  if (!mid) return []

  const haystack = ownedBy ? `${mid} ${ownedBy}` : mid
  if (NON_IMPORTABLE.test(haystack)) return []

  if (IMAGE_GEN.test(mid)) return ['image_gen']
  if (VIDEO.test(mid)) return ['video']
  if (VISION_CHAT.test(mid)) return ['text', 'image']
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
