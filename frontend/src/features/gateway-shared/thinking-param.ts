/**
 * 思考模式参数（与后端 GatewayModel.tags.thinking_param 对齐）
 *
 * 权威来源：API ``selector_capabilities.thinking_param``（由后端 domain 推断并持久化）。
 * 仅当模型列表未加载时，才用模型名做弱兜底（不含 provider，可能不准）。
 *
 * 供 Guide、Playground、模型列表等 Gateway 子功能共用，勿放在 gateway-guide 包内。
 */

export type ThinkingParam =
  | 'none'
  | 'dashscope_enable_thinking'
  | 'builtin_reasoning'
  | 'anthropic_extended'

const THINKING_PARAMS: readonly ThinkingParam[] = [
  'none',
  'dashscope_enable_thinking',
  'builtin_reasoning',
  'anthropic_extended',
]

function isThinkingParam(value: unknown): value is ThinkingParam {
  return typeof value === 'string' && (THINKING_PARAMS as readonly string[]).includes(value)
}

/** 仅从 API 能力字段读取；无 tag 时返回 null（不做 supports_reasoning 猜测）。 */
export function thinkingParamFromCapabilities(
  capabilities?: Record<string, unknown>
): ThinkingParam | null {
  const raw = capabilities?.thinking_param
  return isThinkingParam(raw) ? raw : null
}

/**
 * 解析当前模型的思考参数：优先 API，其次模型名弱兜底（列表未命中时）。
 */
export function resolveThinkingParamForModel(
  modelName: string,
  capabilities?: Record<string, unknown>
): ThinkingParam {
  const fromApi = thinkingParamFromCapabilities(capabilities)
  if (fromApi !== null) return fromApi

  const lower = modelName.trim().toLowerCase()
  if (!lower) return 'none'
  if (lower.includes('qwen3') || lower.includes('qwen-3')) {
    return 'dashscope_enable_thinking'
  }
  if (lower.includes('qwq') || lower.includes('reasoner')) {
    return 'builtin_reasoning'
  }
  return 'none'
}

/** 模型列表芯片展示文案 */
export function thinkingParamLabel(param: ThinkingParam): string | null {
  switch (param) {
    case 'dashscope_enable_thinking':
      return 'Qwen3 思考'
    case 'builtin_reasoning':
      return '内置推理'
    case 'anthropic_extended':
      return 'Extended Thinking'
    default:
      return null
  }
}

export function thinkingHintForModel(
  modelName: string,
  apiFlavor: 'openai' | 'anthropic',
  capabilities?: Record<string, unknown>
): string | null {
  const param = resolveThinkingParamForModel(modelName, capabilities)
  const fromApi = thinkingParamFromCapabilities(capabilities) !== null

  if (param === 'none') {
    return `当前模型「${modelName}」通常不支持思考模式；请勿对普通模型传 enable_thinking / thinking。`
  }
  if (apiFlavor === 'anthropic') {
    if (param === 'anthropic_extended') {
      return `当前模型「${modelName}」：推荐在请求体使用 thinking: { type: "enabled", budget_tokens: 8000 }。`
    }
    return `当前模型「${modelName}」：Anthropic 原生 thinking 通常用于 Claude；请确认模型能力。`
  }
  switch (param) {
    case 'dashscope_enable_thinking':
      return `当前模型「${modelName}」：推荐 stream: true + extra_body.enable_thinking: true；非流式须 enable_thinking: false。${fromApi ? '' : '（能力来自模型名推断，请以模型列表标签为准）'}`
    case 'builtin_reasoning':
      return `当前模型「${modelName}」：内置推理，无需 enable_thinking；流式/非流式均可读 reasoning_content。`
    default:
      return null
  }
}

/** Playground：内置推理模型说明（无请求开关） */
export function builtinReasoningPlaygroundHint(param: ThinkingParam): string | null {
  if (param !== 'builtin_reasoning') return null
  return '内置推理模型：无需开启思考模式开关，响应中的 reasoning_content 会自动展示。'
}
