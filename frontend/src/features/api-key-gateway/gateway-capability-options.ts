/**
 * Gateway 代理能力白名单（与后端 GATEWAY_PROXY_CAPABILITY_VALUES 对齐）
 */

export const GATEWAY_PROXY_CAPABILITIES = [
  { value: 'chat', label: '对话 (chat)' },
  { value: 'embedding', label: '嵌入 (embedding)' },
  { value: 'image', label: '图像 (image)' },
  { value: 'audio_transcription', label: '语音转写' },
  { value: 'audio_speech', label: '语音合成' },
  { value: 'rerank', label: '重排序 (rerank)' },
  { value: 'video_generation', label: '视频生成' },
  { value: 'moderation', label: '内容审核' },
] as const

export type GatewayProxyCapability = (typeof GATEWAY_PROXY_CAPABILITIES)[number]['value']

export interface GrantPolicyValues {
  allowed_models: string[]
  allowed_capabilities: string[]
  rpm_limit: number | null
  tpm_limit: number | null
  store_full_messages: boolean
  guardrail_enabled: boolean
}

export const EMPTY_GRANT_POLICY: GrantPolicyValues = {
  allowed_models: [],
  allowed_capabilities: [],
  rpm_limit: null,
  tpm_limit: null,
  store_full_messages: false,
  guardrail_enabled: false,
}
