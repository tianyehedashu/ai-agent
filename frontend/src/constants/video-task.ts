/**
 * 视频任务相关常量 - 与后端 video_task 能力保持一致，避免多处重复定义
 */

import type { VideoModel, VideoDuration } from '@/types/video-task'

export interface VideoModelOption {
  value: VideoModel
  label: string
  description?: string
}

export const VIDEO_MODELS: VideoModelOption[] = [
  { value: 'openai::sora1.0', label: 'Sora 1.0', description: '快速生成' },
  { value: 'openai::sora2.0', label: 'Sora 2.0', description: '高质量' },
]

export function getVideoDurations(model: VideoModel): VideoDuration[] {
  if (model === 'openai::sora2.0') return [5, 10, 15]
  return [5, 10, 15, 20]
}

export interface MarketplaceOption {
  value: string
  label: string
  flag: string
}

/** 支持的市场/站点列表（value 与后端 marketplace 一致） */
export const VIDEO_TASK_MARKETPLACES: MarketplaceOption[] = [
  { value: 'jp', label: '🇯🇵 日本', flag: '🇯🇵' },
  { value: 'us', label: '🇺🇸 美国', flag: '🇺🇸' },
  { value: 'de', label: '🇩🇪 德国', flag: '🇩🇪' },
  { value: 'uk', label: '🇬🇧 英国', flag: '🇬🇧' },
  { value: 'fr', label: '🇫🇷 法国', flag: '🇫🇷' },
  { value: 'it', label: '🇮🇹 意大利', flag: '🇮🇹' },
  { value: 'es', label: '🇪🇸 西班牙', flag: '🇪🇸' },
]

/** 由 MARKETPLACES 派生的 value -> flag 映射，用于列表/详情展示 */
export const VIDEO_TASK_MARKETPLACE_FLAGS: Record<string, string> = Object.fromEntries(
  VIDEO_TASK_MARKETPLACES.map((m) => [m.value, m.flag])
)

/** 示例提示词（简短标签 + 完整描述），用于视频任务页与聊天内视频表单 */
export const VIDEO_TASK_EXAMPLE_PROMPTS: { short: string; full: string }[] = [
  { short: '咖啡机', full: '一款精致的咖啡机，展示研磨咖啡豆、萃取浓缩咖啡的全过程' },
  { short: '智能手表', full: '智能手表在手腕上，展示表盘切换、心率监测、消息提醒功能' },
  { short: '无线耳机', full: '无线耳机从充电盒中取出，佩戴入耳，展示触控操作和降噪效果' },
  { short: '护肤精华', full: '护肤精华液滴落在手背，轻柔涂抹，展示吸收过程和肌肤光泽' },
]
