/**
 * Playground / 调用指南共用的示例 prompt 与参考图 URL
 */

import type { PlaygroundMode } from './playground-mode-filter'

export const PLAYGROUND_EXAMPLE_PROMPTS: Record<PlaygroundMode, string> = {
  chat: '请用三句话介绍 AI Gateway 的作用，并给出一个适合接入的场景。',
  vision: '请用三点总结图片内容，识别主要物体、场景关系和任何可能的风险。',
  image_gen:
    '写实风格的 SaaS 产品发布海报，主体是一台展示 AI Gateway 控制台的笔记本电脑，蓝紫渐变背景，干净科技感，16:9。',
  video_gen:
    '生成一段 6 秒产品演示短视频：镜头从团队仪表盘推进到模型调用日志，风格简洁、科技感、平滑运镜。',
}

export const PLAYGROUND_EXAMPLE_PROMPT_VALUES = new Set<string>(
  Object.values(PLAYGROUND_EXAMPLE_PROMPTS)
)

export const PLAYGROUND_EXAMPLE_IMAGE_URL = 'https://example.com/photo.jpg'
export const PLAYGROUND_EXAMPLE_VIDEO_REF_URL = 'https://example.com/reference.jpg'
