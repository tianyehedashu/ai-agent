/**
 * 思考模式 UI 文案与 Playground 提示（能力解析见 model-selector-capabilities）。
 */

import {
  resolveThinkingParamForModel,
  thinkingParamFromCapabilities,
  type ThinkingParam,
} from './model-selector-capabilities'

export type { ThinkingParam } from './model-selector-capabilities'
export {
  resolveThinkingParamForModel,
  thinkingParamFromCapabilities,
} from './model-selector-capabilities'

/** 模型列表芯片展示文案 */
export function thinkingParamLabel(param: ThinkingParam): string | null {
  switch (param) {
    case 'dashscope_enable_thinking':
      return 'Qwen3 思考'
    case 'builtin_reasoning':
      return '内置推理'
    case 'anthropic_extended':
      return 'Extended Thinking'
    case 'deepseek_v4_thinking':
      return 'V4 思考'
    default:
      return null
  }
}

export function thinkingHintForModel(
  modelName: string,
  apiFlavor: 'openai' | 'anthropic',
  capabilities?: Record<string, unknown>,
  options?: { allowNameFallback?: boolean }
): string | null {
  const param = resolveThinkingParamForModel(modelName, capabilities, options)
  const fromApi = thinkingParamFromCapabilities(capabilities) !== null

  if (param === 'none') {
    return `当前模型「${modelName}」通常不支持思考模式；请勿对普通模型传 enable_thinking / thinking。`
  }
  if (apiFlavor === 'anthropic') {
    if (param === 'anthropic_extended') {
      return `当前模型「${modelName}」：推荐在请求体使用 thinking: { type: "enabled", budget_tokens: 8000 }。`
    }
    if (param === 'deepseek_v4_thinking') {
      return `当前模型「${modelName}」为 DeepSeek V4，请使用 OpenAI 兼容入口并传 extra_body.thinking（Anthropic 入口不适用）。`
    }
    return `当前模型「${modelName}」：Anthropic 原生 thinking 通常用于 Claude；请确认模型能力。`
  }
  switch (param) {
    case 'dashscope_enable_thinking':
      return `当前模型「${modelName}」：推荐 stream: true + enable_thinking / extra_body.enable_thinking: true；非流式须 enable_thinking: false。${fromApi ? '' : '（能力来自模型名推断，请以模型列表标签为准）'}`
    case 'builtin_reasoning':
      return `当前模型「${modelName}」：内置推理，无需 enable_thinking；流式/非流式均可读 reasoning_content。`
    case 'deepseek_v4_thinking':
      return `当前模型「${modelName}」：推荐 extra_body.thinking: { type: "enabled" }（可选 reasoning_effort: "high"）；响应含 reasoning_content。${fromApi ? '' : '（能力来自模型名推断，请以模型列表标签为准）'}`
    default:
      return null
  }
}

/** Playground：内置推理模型说明（无请求开关） */
export function builtinReasoningPlaygroundHint(param: ThinkingParam): string | null {
  if (param !== 'builtin_reasoning') return null
  return '内置推理模型：无需开启思考模式开关，响应中的 reasoning_content 会自动展示。'
}
