/**
 * 产出预览相关纯函数（独立文件以满足 react-refresh/only-export-components）
 */

import { PRODUCT_INFO_BULLET_KEYS } from '@/constants/product-info'
import type { ProductImageGenTask } from '@/types/product-info'

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

/** 从列表中取当前 job 最近一次 8 图结果（按 job_id 优先，否则取最新一条有图的） */
export function pickLatestEightImages(
  tasks: ProductImageGenTask[],
  jobId: string | null
): { slot: number; url: string }[] | null {
  const withImages = tasks.filter((t) => t.result_images && t.result_images.length > 0)
  const byJob = jobId ? withImages.filter((t) => t.job_id === jobId) : []
  const list = byJob.length > 0 ? byJob : withImages
  const task = list.at(0)
  if (task === undefined) return null
  return task.result_images ?? null
}
