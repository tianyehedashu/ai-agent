/**
 * 与后端 ``selector_capabilities`` / ``ModelCapabilitySnapshot`` 对齐的类型与读取。
 */

export type ThinkingParam =
  | 'none'
  | 'dashscope_enable_thinking'
  | 'builtin_reasoning'
  | 'anthropic_extended'
  | 'deepseek_v4_thinking'

const THINKING_PARAMS: readonly ThinkingParam[] = [
  'none',
  'dashscope_enable_thinking',
  'builtin_reasoning',
  'anthropic_extended',
  'deepseek_v4_thinking',
]

export type TemperaturePolicy = 'client' | 'fixed_1' | 'probe_0'

export interface ModelSelectorCapabilities {
  supports_vision?: boolean
  supports_tools?: boolean
  supports_reasoning?: boolean
  thinking_param?: ThinkingParam
  temperature_policy?: TemperaturePolicy
  temperature_default?: number
  supports_json_mode?: boolean
  supports_image_gen?: boolean
  supports_txt2img?: boolean
  supports_img2img?: boolean
  supports_video_gen?: boolean
  supports_image_to_video?: boolean
  max_reference_images?: number
}

export function parseSelectorCapabilities(
  raw?: Record<string, unknown>
): ModelSelectorCapabilities | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  return raw as ModelSelectorCapabilities
}

function isThinkingParam(value: unknown): value is ThinkingParam {
  return typeof value === 'string' && (THINKING_PARAMS as readonly string[]).includes(value)
}

/** 仅从 API 能力字段读取；无 tag 时返回 null。 */
export function thinkingParamFromCapabilities(
  capabilities?: Record<string, unknown>
): ThinkingParam | null {
  const raw = capabilities?.thinking_param
  return isThinkingParam(raw) ? raw : null
}

/**
 * 解析当前模型的思考参数：优先 API ``selector_capabilities``；
 * ``allowNameFallback: false`` 时列表已加载，禁止模型名弱推断。
 */
export function resolveThinkingParamForModel(
  modelName: string,
  capabilities?: Record<string, unknown>,
  options?: { allowNameFallback?: boolean }
): ThinkingParam {
  const fromApi = thinkingParamFromCapabilities(capabilities)
  if (fromApi !== null) return fromApi
  if (options?.allowNameFallback === false) return 'none'

  const lower = modelName.trim().toLowerCase()
  if (!lower) return 'none'
  if (lower.includes('qwen3') || lower.includes('qwen-3')) {
    return 'dashscope_enable_thinking'
  }
  if (lower.includes('qwq') || lower.includes('reasoner')) {
    return 'builtin_reasoning'
  }
  // 弱推断：须与 backend thinking_param.is_deepseek_v4_model_id 同步
  if (/deepseek-v4-(pro|flash)/.test(lower)) {
    return 'deepseek_v4_thinking'
  }
  return 'none'
}

export function temperaturePolicyFromCapabilities(
  capabilities?: Record<string, unknown>
): TemperaturePolicy | null {
  const policy = capabilities?.temperature_policy
  if (policy === 'client' || policy === 'fixed_1' || policy === 'probe_0') {
    return policy
  }
  return null
}

export function temperatureDefaultFromCapabilities(capabilities?: Record<string, unknown>): number {
  const raw = capabilities?.temperature_default
  if (typeof raw === 'number' && raw >= 0 && raw <= 2) return raw
  return 0.7
}
