/**
 * 产出预览相关纯函数（独立文件以满足 react-refresh/only-export-components）
 */

import { PRODUCT_INFO_BULLET_KEYS } from '@/constants/listing-studio'
import type { ProductImageGenTask } from '@/types/listing-studio'

export const EIGHT_IMAGE_SLOT_COUNT = 8

/** 从 product_info 输出中解析出最多 5 条商品描述 */
export function getFivePointDescription(productInfo: unknown): string[] {
  if (!productInfo || typeof productInfo !== 'object') return []
  const obj = productInfo as Record<string, unknown>
  for (const key of PRODUCT_INFO_BULLET_KEYS) {
    const val = obj[key]
    if (Array.isArray(val)) {
      return val
        .slice(0, 5)
        .map((v) => (typeof v === 'string' ? v : String(v)).trim())
        .filter(Boolean)
    }
  }
  const raw = obj.raw_text
  if (typeof raw === 'string' && raw.trim()) {
    return raw
      .split(/\n+/)
      .map((s) => s.replace(/^[\s\-*·]\s*/, '').trim())
      .filter(Boolean)
      .slice(0, 5)
  }
  return []
}

function taskTimestamp(task: ProductImageGenTask): number {
  const raw = task.created_at
  if (!raw) return 0
  const ms = Date.parse(raw)
  return Number.isNaN(ms) ? 0 : ms
}

function pickTasksForJob(
  tasks: ProductImageGenTask[],
  jobId: string | null
): ProductImageGenTask[] {
  const withImages = tasks.filter((t) => t.result_images && t.result_images.length > 0)
  if (jobId) {
    const byJob = withImages.filter((t) => t.job_id === jobId)
    if (byJob.length > 0) return byJob
  }
  return withImages
}

/** 跨 task 按槽位合并：每个 slot 取最新 task 中的有效 url */
export function pickLatestEightImages(
  tasks: ProductImageGenTask[],
  jobId: string | null
): { slot: number; url: string }[] | null {
  const relevant = pickTasksForJob(tasks, jobId)
  if (relevant.length === 0) return null

  const sorted = [...relevant].sort((a, b) => taskTimestamp(b) - taskTimestamp(a))
  const slotUrl = new Map<number, string>()

  for (const task of sorted) {
    for (const img of task.result_images ?? []) {
      const slot = img.slot
      const url = img.url.trim()
      if (!url || slotUrl.has(slot)) continue
      slotUrl.set(slot, url)
    }
  }

  if (slotUrl.size === 0) return null

  const merged: { slot: number; url: string }[] = []
  for (let slot = 1; slot <= EIGHT_IMAGE_SLOT_COUNT; slot += 1) {
    const url = slotUrl.get(slot)
    if (url) merged.push({ slot, url })
  }
  return merged.length > 0 ? merged : null
}

/** 将合并结果转为 8 槽数组（index 0 = slot 1） */
export function mergedImagesToSlotArray(
  merged: { slot: number; url: string }[] | null
): (string | null)[] {
  const slots: (string | null)[] = Array.from({ length: EIGHT_IMAGE_SLOT_COUNT }, () => null)
  if (!merged) return slots
  for (const img of merged) {
    if (img.slot >= 1 && img.slot <= EIGHT_IMAGE_SLOT_COUNT) {
      slots[img.slot - 1] = img.url
    }
  }
  return slots
}
