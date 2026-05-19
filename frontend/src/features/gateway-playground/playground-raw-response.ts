import type {
  PlaygroundImageRawSummary,
  PlaygroundRawResponse,
  PlaygroundVideoRawSummary,
} from './types'

export function isImageGenRaw(raw: PlaygroundRawResponse): raw is PlaygroundImageRawSummary {
  return (
    raw !== null &&
    typeof raw === 'object' &&
    'type' in raw &&
    (raw as { type: unknown }).type === 'image_gen'
  )
}

export function isVideoGenRaw(raw: PlaygroundRawResponse): raw is PlaygroundVideoRawSummary {
  return (
    raw !== null &&
    typeof raw === 'object' &&
    'type' in raw &&
    (raw as { type: unknown }).type === 'video_gen'
  )
}

export function safeStringify(value: unknown): string {
  if (value === null || value === undefined) return '（无）'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    if (typeof value === 'string') return value
    if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
      return String(value)
    }
    return '[unserializable]'
  }
}
