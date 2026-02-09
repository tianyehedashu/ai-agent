/**
 * 工具结果块渲染用工具
 *
 * 用于从 process run 的 tool_result 中解析出「按类型展示」所需的字段，
 * 供 ProcessPanel 等根据工具名 + 解析结果选择展示组件。
 */

/** 返回 JSON 中带 task_id 的视频类工具名 */
export const VIDEO_TASK_TOOL_NAMES = [
  'amazon_video_submit',
  'amazon_video_poll',
] as const

export type VideoTaskToolName = (typeof VIDEO_TASK_TOOL_NAMES)[number]

export function isVideoTaskToolName(name: string): name is VideoTaskToolName {
  return (VIDEO_TASK_TOOL_NAMES as readonly string[]).includes(name)
}

/** 从工具 output 字符串中解析视频任务 ID（后端返回 JSON 含 task_id） */
export function parseVideoTaskOutput(output: string): { taskId: string } | null {
  if (typeof output !== 'string' || !output.trim()) return null
  try {
    const data = JSON.parse(output) as Record<string, unknown>
    const taskId = data?.task_id
    if (typeof taskId === 'string' && taskId) return { taskId }
    return null
  } catch {
    return null
  }
}
