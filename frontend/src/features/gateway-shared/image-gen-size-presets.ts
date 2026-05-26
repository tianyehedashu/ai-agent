/**
 * 生图尺寸预设（Playground / Listing Studio 共用）。
 *
 * - OpenAI DALL·E 类：仅支持固定三种 WxH（等价于比例选择）。
 * - 火山 Seedream 4.5+：总像素 ≥ 3_686_400，比例约 1:16～16:1，边长建议 128 对齐。
 */

export interface ImageGenSizePreset {
  id: string
  /** 场景向短标签，如「正方形」「横版海报」 */
  label: string
  /** 展示用比例文案 */
  aspect: string
  /** API ``size`` 字段 */
  size: string
  /** 宽/高，供 UI ``aspect-ratio`` */
  aspectRatio: number
  width: number
  height: number
}

function preset(
  id: string,
  label: string,
  aspect: string,
  width: number,
  height: number
): ImageGenSizePreset {
  return {
    id,
    label,
    aspect,
    size: `${String(width)}x${String(height)}`,
    aspectRatio: width / height,
    width,
    height,
  }
}

/** OpenAI ``images/generations`` 常用固定尺寸（DALL·E 3 风格三档） */
export const OPENAI_IMAGE_GEN_PRESETS: readonly ImageGenSizePreset[] = [
  preset('openai_square', '正方形', '1:1', 1024, 1024),
  preset('openai_portrait', '竖版', '9:16', 1024, 1792),
  preset('openai_landscape', '横版', '16:9', 1792, 1024),
] as const

/**
 * 火山 Seedream：满足 ≥ 3_686_400 像素且 128 对齐的常用电商/海报比例。
 * 勿使用 1080×1920 / 1920×1080（仅 ~2.1MP，会触发上游 400）。
 */
export const VOLCENGINE_IMAGE_GEN_PRESETS: readonly ImageGenSizePreset[] = [
  preset('volc_square', '正方形', '1:1', 1920, 1920),
  preset('volc_square_2k', '正方形 2K', '1:1', 2048, 2048),
  preset('volc_landscape', '横版', '16:9', 2944, 1664),
  preset('volc_portrait', '竖版', '9:16', 1536, 2688),
  preset('volc_standard_landscape', '标准横', '4:3', 2304, 1728),
  preset('volc_standard_portrait', '标准竖', '3:4', 1728, 2304),
] as const

export const VOLCENGINE_MIN_IMAGE_PIXELS = 3_686_400

export function isVolcengineImageProvider(provider: string | undefined): boolean {
  return provider?.trim().toLowerCase() === 'volcengine'
}

export function imageGenPresetsForProvider(
  provider: string | undefined
): readonly ImageGenSizePreset[] {
  if (isVolcengineImageProvider(provider)) return VOLCENGINE_IMAGE_GEN_PRESETS
  return OPENAI_IMAGE_GEN_PRESETS
}

export function defaultImageGenPresetForProvider(provider: string | undefined): ImageGenSizePreset {
  return imageGenPresetsForProvider(provider)[0]
}

export function defaultImageGenSizeForProvider(provider: string | undefined): string {
  return defaultImageGenPresetForProvider(provider).size
}

export function imageGenPresetBySize(
  provider: string | undefined,
  size: string
): ImageGenSizePreset | undefined {
  const normalized = size.trim().toLowerCase()
  return imageGenPresetsForProvider(provider).find((p) => p.size.toLowerCase() === normalized)
}

export function imageGenSizesForProvider(provider: string | undefined): readonly string[] {
  return imageGenPresetsForProvider(provider).map((p) => p.size)
}

export function imageGenProviderSizeHint(provider: string | undefined): string | null {
  if (!isVolcengineImageProvider(provider)) return null
  return '火山 Seedream 要求总像素 ≥ 3.7MP（如 1920×1920）；竖/横版请选下方预设比例。'
}
