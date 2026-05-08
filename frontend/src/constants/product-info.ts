/**
 * 产品信息页 - 能力与输入字段常量（与后端 capability_id 一致）
 */

import type { ModelType } from '@/types/user-model'

export const CAPABILITY_ORDER = [
  'image_analysis',
  'product_link_analysis',
  'competitor_link_analysis',
  'video_script',
  'image_gen_prompts',
] as const

export type CapabilityId = (typeof CAPABILITY_ORDER)[number]

export const CAPABILITY_NAMES: Record<string, string> = {
  image_analysis: '图片分析',
  product_link_analysis: '商品链接分析',
  competitor_link_analysis: '竞品链接分析',
  video_script: '视频脚本/分镜',
  image_gen_prompts: '8 图生成提示词',
}

/** 各能力输出在 output_snapshot 中的主键 */
export const OUTPUT_KEYS: Record<string, string> = {
  image_analysis: 'image_descriptions',
  product_link_analysis: 'product_info',
  competitor_link_analysis: 'competitor_info',
  video_script: 'video_script',
  image_gen_prompts: 'prompts',
}

/** product_info 中可能表示 5 点商品描述的字段（按优先级尝试） */
export const PRODUCT_INFO_BULLET_KEYS = [
  'bullet_points',
  'five_point_description',
  'key_points',
  '卖点',
  'selling_points',
] as const

/** 分类输入字段（与 run_step user_input 对应） */
export const INPUT_FIELDS = [
  { key: 'product_link', label: '产品链接', placeholder: 'https://...' },
  { key: 'competitor_link', label: '竞品链接', placeholder: 'https://...' },
  { key: 'product_name', label: '产品名称', placeholder: '商品名称或 ASIN' },
  { key: 'keywords', label: '关键词', placeholder: '逗号或空格分隔' },
] as const

export const INPUT_IMAGE_URLS_KEY = 'image_urls' as const

/** 产品信息页输入区默认值（便于演示与快速填写） */
export const DEFAULT_PRODUCT_INFO_INPUTS: {
  product_link?: string
  competitor_link?: string
  product_name?: string
  keywords?: string
  image_urls?: string[]
} = {
  product_link: 'https://detail.1688.com/offer/900277932787.html',
  competitor_link: 'https://www.amazon.co.jp/-/zh/dp/B0FC1NK9DN',
  product_name: '电动连发玩具枪',
  keywords: '电动连发玩具枪',
  image_urls: [
    'https://cbu01.alicdn.com/img/ibank/O1CN014FI1h11UaAHCj1lOl_!!2206750852533-0-cib.jpg',
  ],
}

/** 每个能力依赖的前步 capability_id（与后端 CAPABILITY_DEPENDENCIES 对齐） */
export const CAPABILITY_DEPENDENCIES: Record<string, string[]> = {
  image_analysis: [],
  product_link_analysis: [],
  competitor_link_analysis: [],
  video_script: ['product_link_analysis', 'competitor_link_analysis'],
  image_gen_prompts: ['product_link_analysis', 'video_script'],
}

/** Job 状态文案映射（统一复用） */
export const JOB_STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  partial: '部分完成',
}

/** 每个能力所需的模型类型（用于 ModelSelector 过滤）。
 *  需要图片理解的能力用 'image'，纯文本用 'text' */
export const CAPABILITY_MODEL_TYPES: Record<string, ModelType> = {
  image_analysis: 'image',
  product_link_analysis: 'text',
  competitor_link_analysis: 'text',
  video_script: 'text',
  image_gen_prompts: 'text',
}

/** 元提示词可用占位符：每能力可引用的输入/输出参数，用于 {{param}} 渲染（与后端 META_PROMPT_PARAMS 对齐） */
export const META_PROMPT_PARAMS: Record<string, { key: string; label: string }[]> = {
  image_analysis: [
    { key: 'product_name', label: '产品名称' },
    { key: 'image_urls', label: '图片链接' },
  ],
  product_link_analysis: [
    { key: 'product_link', label: '产品链接' },
    { key: 'product_name', label: '产品名称' },
    { key: 'keywords', label: '关键词' },
  ],
  competitor_link_analysis: [
    { key: 'competitor_link', label: '竞品链接' },
    { key: 'product_name', label: '产品名称' },
    { key: 'product_info', label: '产品信息（前步）' },
  ],
  video_script: [
    { key: 'product_name', label: '产品名称' },
    { key: 'keywords', label: '关键词' },
    { key: 'product_info', label: '产品信息（前步）' },
    { key: 'competitor_info', label: '竞品信息（前步）' },
  ],
  image_gen_prompts: [
    { key: 'product_name', label: '产品名称' },
    { key: 'product_info', label: '产品信息（前步）' },
    { key: 'competitor_info', label: '竞品信息（前步）' },
    { key: 'video_script', label: '视频脚本（前步）' },
    { key: 'image_descriptions', label: '图片描述（前步）' },
  ],
}

/** 每个能力使用的用户输入字段（用于 StepContextPanel 展示相关字段） */
export const CAPABILITY_INPUT_FIELDS: Record<string, string[]> = {
  image_analysis: ['image_urls', 'product_name'],
  product_link_analysis: ['product_link', 'product_name', 'keywords'],
  competitor_link_analysis: ['competitor_link', 'product_name'],
  video_script: ['product_name', 'keywords'],
  image_gen_prompts: ['product_name'],
}
