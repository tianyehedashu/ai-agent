/**
 * 图片/视频生成响应解析（兼容 OpenAI 形与 LiteLLM 常见变体）
 */

export interface ParsedImageItem {
  url?: string
  b64Json?: string
  revisedPrompt?: string
}

export interface ParsedVideoResult {
  url?: string
  summary: string
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

export function parseImageGenerationResponse(json: unknown): ParsedImageItem[] {
  const root = asRecord(json)
  if (!root) return []
  const data = root.data
  if (!Array.isArray(data)) return []
  const items: ParsedImageItem[] = []
  for (const row of data) {
    const item = asRecord(row)
    if (!item) continue
    const url = typeof item.url === 'string' ? item.url : undefined
    const b64 =
      typeof item.b64_json === 'string'
        ? item.b64_json
        : typeof item.b64Json === 'string'
          ? item.b64Json
          : undefined
    const revised =
      typeof item.revised_prompt === 'string'
        ? item.revised_prompt
        : typeof item.revisedPrompt === 'string'
          ? item.revisedPrompt
          : undefined
    if (url || b64) {
      items.push({ url, b64Json: b64, revisedPrompt: revised })
    }
  }
  return items
}

export function imageItemsToDisplayContent(items: ParsedImageItem[]): string {
  if (items.length === 0) return '（未解析到图片 URL 或 base64，请查看响应 JSON）'
  return items
    .map((item, i) => {
      const parts = [`# 图片 ${String(i + 1)}`]
      if (item.url) parts.push(`URL: ${item.url}`)
      if (item.b64Json) parts.push('（含 base64 数据，见预览或响应 JSON）')
      if (item.revisedPrompt) parts.push(`修订提示: ${item.revisedPrompt}`)
      return parts.join('\n')
    })
    .join('\n\n')
}

export function parseVideoGenerationResponse(json: unknown): ParsedVideoResult {
  const root = asRecord(json)
  if (!root) {
    return { summary: '（无法解析响应）' }
  }
  const directUrl = typeof root.url === 'string' ? root.url : undefined
  if (directUrl) {
    return { url: directUrl, summary: `视频 URL: ${directUrl}` }
  }
  const video = asRecord(root.video)
  if (video && typeof video.url === 'string') {
    return { url: video.url, summary: `视频 URL: ${video.url}` }
  }
  const data = root.data
  if (Array.isArray(data) && data.length > 0) {
    const first = asRecord(data[0])
    if (first && typeof first.url === 'string') {
      return { url: first.url, summary: `视频 URL: ${first.url}` }
    }
  }
  return { summary: '（未解析到视频 URL，请查看响应 JSON）' }
}

export function imageSrcFromItem(item: ParsedImageItem): string | undefined {
  if (item.url) return item.url
  if (item.b64Json) {
    const raw = item.b64Json.trim()
    if (raw.startsWith('data:')) return raw
    return `data:image/png;base64,${raw}`
  }
  return undefined
}
