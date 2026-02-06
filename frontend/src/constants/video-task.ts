/**
 * 视频任务相关常量 - 与后端 video_task 能力保持一致，避免多处重复定义
 */

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
