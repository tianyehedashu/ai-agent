/**
 * 与 InputPanel 相关的类型与纯函数（单独文件以满足 react-refresh/only-export-components）
 */

import type { ComponentType } from 'react'

import { Link2, Package, Tags } from '@/lib/lucide-icons'
import type { ListingStudioInputs, RunStepBody } from '@/types/listing-studio'

export type { ListingStudioInputs }

export const FIELD_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  product_link: Link2,
  competitor_link: Link2,
  product_name: Package,
  keywords: Tags,
}

const INPUT_LABELS: Record<string, string> = {
  product_link: '产品链接',
  competitor_link: '竞品链接',
  product_name: '产品名称',
  keywords: '关键词',
  image_urls: '图片',
}

type TextInputKey = Exclude<keyof ListingStudioInputs, 'image_urls'>

/** 读取文本类输入字段 */
export function getTextInputValue(inputs: ListingStudioInputs, key: TextInputKey): string {
  return inputs[key] ?? ''
}

/** 转为 run_step 的 user_input */
export function inputsToUserInput(inputs: ListingStudioInputs): RunStepBody['user_input'] {
  const out: Record<string, unknown> = {}
  if (inputs.product_link) out.product_link = inputs.product_link
  if (inputs.competitor_link) out.competitor_link = inputs.competitor_link
  if (inputs.product_name) out.product_name = inputs.product_name
  if (inputs.keywords) out.keywords = inputs.keywords
  if (inputs.image_urls?.length) out.image_urls = inputs.image_urls
  return out
}

/** 用于折叠区标题的简短摘要：已填写的输入项 */
export function getInputSummary(inputs: ListingStudioInputs): string {
  const filled: string[] = []
  if (inputs.product_link) filled.push(INPUT_LABELS.product_link)
  if (inputs.competitor_link) filled.push(INPUT_LABELS.competitor_link)
  if (inputs.product_name) filled.push(INPUT_LABELS.product_name)
  if (inputs.keywords) filled.push(INPUT_LABELS.keywords)
  if (inputs.image_urls?.length) {
    filled.push(`${INPUT_LABELS.image_urls} ${String(inputs.image_urls.length)} 张`)
  }
  return filled.length ? `已填 ${filled.join('、')}` : '未填'
}
