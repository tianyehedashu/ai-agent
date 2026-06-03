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
 * 复制文本到剪贴板，优先 Clipboard API，fallback 到 execCommand
 *
 * - Clipboard API 在非 HTTPS（如 HTTP localhost）或非焦点窗口中会抛异常
 * - execCommand('copy') 虽已标记 deprecated，但兼容性最好
 */
export async function copyToClipboard(text: string): Promise<void> {
  // 优先使用 Clipboard API
  try {
    await navigator.clipboard.writeText(text)
    return
  } catch {
    // Clipboard API 不可用，fallback 到 execCommand
  }

  // Fallback：创建隐藏 textarea + execCommand('copy')
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  try {
    // eslint-disable-next-line @typescript-eslint/no-deprecated -- execCommand is the only fallback for non-HTTPS contexts
    const ok = document.execCommand('copy')
    if (!ok) throw new Error('execCommand copy returned false')
  } finally {
    document.body.removeChild(textarea)
  }
}

export function generateId(): string {
  return Math.random().toString(36).substring(2, 15)
}
