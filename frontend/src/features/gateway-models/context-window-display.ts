import type { GatewayModelListItem } from './list/types'

/** 优先 selector_capabilities，回退 tags；非正整数视为未知（0）。 */
export function resolveContextWindow(
  sc: Record<string, unknown> | undefined,
  tags?: Record<string, unknown> | null
): number {
  for (const raw of [sc?.context_window, tags?.context_window]) {
    if (typeof raw === 'number' && Number.isInteger(raw) && raw > 0) {
      return raw
    }
  }
  return 0
}

/** 262144 → "256K"；1000000 → "1M"。 */
export function formatContextWindow(tokens: number): string {
  if (tokens >= 1_000_000 && tokens % 1_000_000 === 0) {
    return `${String(tokens / 1_000_000)}M`
  }
  if (tokens >= 1024 && tokens % 1024 === 0) {
    return `${String(tokens / 1024)}K`
  }
  if (tokens >= 1000) {
    return `${String(Math.round(tokens / 1000))}K`
  }
  return String(tokens)
}

/** 能力编辑器回显；'' 表示未设置。 */
export function contextWindowEditorValue(
  sc?: Record<string, unknown> | null,
  tags?: Record<string, unknown> | null
): string {
  const tokens = resolveContextWindow(sc ?? undefined, tags)
  return tokens > 0 ? String(tokens) : ''
}

/** 列表列 / tooltip 用；未设置返回 "—"。 */
export function listContextWindowLabel(item: GatewayModelListItem): string {
  const tokens = resolveContextWindow(item.selectorCapabilities)
  if (!tokens) return '—'
  return formatContextWindow(tokens)
}

/** 能力芯片文案；未设置返回 null。 */
export function contextWindowBadgeLabel(
  sc: Record<string, unknown> | undefined,
  tags?: Record<string, unknown> | null
): string | null {
  const tokens = resolveContextWindow(sc, tags)
  if (!tokens) return null
  return `上下文 ${formatContextWindow(tokens)}`
}
