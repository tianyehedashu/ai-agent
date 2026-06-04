import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

export function formatDate(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

export function formatRelativeTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date
  const now = new Date()
  const diffInSeconds = Math.floor((now.getTime() - d.getTime()) / 1000)

  if (diffInSeconds < 60) return '刚刚'
  if (diffInSeconds < 3600) return `${String(Math.floor(diffInSeconds / 60))} 分钟前`
  if (diffInSeconds < 86400) return `${String(Math.floor(diffInSeconds / 3600))} 小时前`
  if (diffInSeconds < 604800) return `${String(Math.floor(diffInSeconds / 86400))} 天前`
  return formatDate(d)
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length) + '...'
}

/**
 * 复制文本到剪贴板
 *
 * Clipboard API 仅在「安全上下文 + 文档拥有焦点」时才可靠工作；
 * 在 HTTP / 失焦 Dialog 中虽不抛异常，但实际不会写入剪贴板。
 * 故先判断条件，否则直接走 execCommand fallback。
 */
export async function copyToClipboard(text: string): Promise<void> {
  const canUseClipboardApi =
    typeof window !== 'undefined' &&
    window.isSecureContext &&
    typeof navigator !== 'undefined' &&
    'clipboard' in navigator &&
    typeof navigator.clipboard.writeText === 'function' &&
    document.hasFocus()
  if (canUseClipboardApi) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // 部分浏览器（如权限被拒）会抛异常，继续 fallback
    }
  }

  if (!fallbackCopyToClipboard(text)) {
    throw new Error('复制到剪贴板失败')
  }
}

/**
 * 同步 fallback：通过隐藏 textarea + execCommand('copy') 实现
 *
 * 关键点：
 * - 必须 append 到 document.body 才能被 select
 * - 用 `position: fixed; top: 0` 避免页面滚动跳动
 * - 移动端需要先 setSelectionRange 才能正确选中
 */
function fallbackCopyToClipboard(text: string): boolean {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '0'
  textarea.style.left = '0'
  textarea.style.width = '1px'
  textarea.style.height = '1px'
  textarea.style.padding = '0'
  textarea.style.border = 'none'
  textarea.style.outline = 'none'
  textarea.style.boxShadow = 'none'
  textarea.style.background = 'transparent'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'

  const previouslyFocused = document.activeElement as HTMLElement | null

  document.body.appendChild(textarea)
  try {
    textarea.focus()
    textarea.select()
    textarea.setSelectionRange(0, text.length)
    // eslint-disable-next-line @typescript-eslint/no-deprecated -- execCommand 是非安全上下文唯一可用的 fallback
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    document.body.removeChild(textarea)
    if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
      previouslyFocused.focus()
    }
  }
}

export function generateId(): string {
  return Math.random().toString(36).substring(2, 15)
}
