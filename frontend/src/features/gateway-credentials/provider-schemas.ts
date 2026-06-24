import { remoteProfilesForProvider } from './provider-profile-catalog'

/**
 * 凭据 provider 与差异化字段的单一事实源。
 *
 * - 与后端 `domains.gateway.domain.types.USER_GATEWAY_CREDENTIAL_PROVIDERS`
 *   以及 `MANAGED_GATEWAY_CREDENTIAL_PROVIDERS` 保持一致；
 * - extra 字段的 `key` 命名需与 `backend/.../litellm_credential_extra_keys.py`
 *   的 LiteLLM 透传白名单完全对齐（避免落库后被静默丢弃）。
 */

export type CredentialFormScope = 'user' | 'team' | 'system'

export type CredentialFieldType = 'text' | 'password' | 'url' | 'textarea' | 'select'

export interface CredentialFieldSpec {
  key: string
  label: string
  placeholder?: string
  type: CredentialFieldType
  options?: ReadonlyArray<{ value: string; label: string }>
  required?: boolean
  helpText?: string
}

/** 与后端 ``upstream_profile_registry`` 对齐的凭据方案（plan/profile）。 */
export interface UpstreamProfileSpec {
  id: string
  label: string
  defaultApiBaseOpenai?: string
  defaultApiBaseAnthropic?: string
  /** Claude Code 等直连 Anthropic 根路径提示 */
  anthropicDirectHint?: string
  probeStrategy?: string
  probeProtocol?: string
  probeSupported?: boolean
}

export interface ProviderCredentialSchema {
  id: string
  label: string
  defaultApiBase?: string
  profiles?: ReadonlyArray<UpstreamProfileSpec>
  apiBaseRequired?: boolean
  apiBasePlaceholder?: string
  apiKeyLabel?: string
  apiKeyPlaceholder?: string
  apiKeyHelpText?: string
  extraFields?: ReadonlyArray<CredentialFieldSpec>
  /** 不声明则默认对所有 scope 可见 */
  availableScopes?: ReadonlyArray<CredentialFormScope>
  /** 给用户更直观的提示（如 "需手填 api_base"） */
  helpText?: string
}

const SCOPES_ALL: ReadonlyArray<CredentialFormScope> = ['user', 'team', 'system']
const SCOPES_MANAGED: ReadonlyArray<CredentialFormScope> = ['team', 'system']

const AWS_REGION_OPTIONS = [
  { value: 'us-east-1', label: 'us-east-1（US East, N. Virginia）' },
  { value: 'us-west-2', label: 'us-west-2（US West, Oregon）' },
  { value: 'ap-northeast-1', label: 'ap-northeast-1（Tokyo）' },
  { value: 'ap-southeast-1', label: 'ap-southeast-1（Singapore）' },
  { value: 'ap-southeast-2', label: 'ap-southeast-2（Sydney）' },
  { value: 'eu-central-1', label: 'eu-central-1（Frankfurt）' },
  { value: 'eu-west-1', label: 'eu-west-1（Ireland）' },
] as const

const VOLCENGINE_REGION_OPTIONS = [
  { value: 'cn-beijing', label: 'cn-beijing（北京）' },
  { value: 'cn-shanghai', label: 'cn-shanghai（上海）' },
  { value: 'ap-southeast-1', label: 'ap-southeast-1（新加坡）' },
] as const

export const PROVIDER_SCHEMAS: readonly ProviderCredentialSchema[] = [
  {
    id: 'openai',
    label: 'OpenAI (GPT)',
    defaultApiBase: 'https://api.openai.com/v1',
    availableScopes: SCOPES_ALL,
    extraFields: [
      {
        key: 'organization',
        label: 'Organization ID',
        placeholder: 'org-xxxxxxxxxxxxxxxx',
        type: 'text',
      },
      {
        key: 'project_id',
        label: 'Project ID',
        placeholder: 'proj_xxxxxxxxxxxxxxxx',
        type: 'text',
        helpText: 'OpenAI Project Key 必填；普通 sk-... key 留空',
      },
    ],
  },
  {
    id: 'anthropic',
    label: 'Anthropic (Claude)',
    defaultApiBase: 'https://api.anthropic.com',
    availableScopes: SCOPES_ALL,
  },
  {
    id: 'azure',
    label: 'Azure OpenAI',
    apiBaseRequired: true,
    apiBasePlaceholder: 'https://<resource>.openai.azure.com',
    availableScopes: SCOPES_MANAGED,
    extraFields: [
      {
        key: 'api_version',
        label: 'API Version',
        placeholder: '2024-08-01-preview',
        type: 'text',
        required: true,
        helpText: '与 Azure OpenAI 部署版本对应，建议使用最新 GA / preview 版本',
      },
    ],
  },
  {
    id: 'bedrock',
    label: 'AWS Bedrock',
    apiKeyLabel: 'AWS Access Key ID',
    apiKeyPlaceholder: 'AKIA...',
    apiKeyHelpText: 'Bedrock 用 access_key_id；密钥与区域填到下方扩展字段',
    availableScopes: SCOPES_MANAGED,
    extraFields: [
      {
        key: 'aws_secret_access_key',
        label: 'AWS Secret Access Key',
        type: 'password',
        required: true,
      },
      {
        key: 'aws_region_name',
        label: 'AWS Region',
        type: 'select',
        required: true,
        options: AWS_REGION_OPTIONS,
      },
      {
        key: 'aws_session_token',
        label: 'AWS Session Token（可选）',
        type: 'password',
        helpText: '使用临时凭据（STS）时填写',
      },
    ],
  },
  {
    id: 'gemini',
    label: 'Google Gemini',
    availableScopes: SCOPES_MANAGED,
    helpText: 'Google AI Studio 提供的 API Key；如使用 Vertex AI 请选 vertex_ai 提供商',
  },
  {
    id: 'vertex_ai',
    label: 'Google Vertex AI',
    availableScopes: SCOPES_MANAGED,
    apiKeyHelpText:
      'Vertex AI 通常用 Service Account JSON 通过 vertex_credentials 字段提供；此处 API Key 可填占位值',
    extraFields: [
      {
        key: 'vertex_project',
        label: 'Vertex Project ID',
        type: 'text',
        required: true,
        placeholder: 'my-gcp-project',
      },
      {
        key: 'vertex_location',
        label: 'Vertex Location',
        type: 'text',
        required: true,
        placeholder: 'us-central1',
      },
      {
        key: 'vertex_credentials',
        label: 'Service Account JSON',
        type: 'textarea',
        helpText: '粘贴完整的 Service Account JSON 文本（将整体加密存储）',
      },
    ],
  },
  {
    id: 'dashscope',
    label: '阿里云 DashScope (通义千问)',
    apiBaseRequired: true,
    defaultApiBase: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    profiles: [
      {
        id: 'dashscope.default',
        label: '北京地域（兼容模式）',
        defaultApiBaseOpenai: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      },
      {
        id: 'dashscope.intl',
        label: '新加坡地域（兼容模式）',
        defaultApiBaseOpenai: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1',
      },
      {
        id: 'dashscope.us',
        label: '美国弗吉尼亚（兼容模式）',
        defaultApiBaseOpenai: 'https://dashscope-us.aliyuncs.com/compatible-mode/v1',
      },
    ],
    availableScopes: SCOPES_ALL,
    extraFields: [
      {
        key: 'workspace_id',
        label: 'Workspace ID（可选）',
        placeholder: 'llm-xxxxxxxxxxxxxxxx',
        type: 'text',
      },
    ],
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    defaultApiBase: 'https://api.deepseek.com/v1',
    availableScopes: SCOPES_ALL,
  },
  {
    id: 'moonshot',
    label: 'Kimi (Moonshot)',
    apiBaseRequired: true,
    defaultApiBase: 'https://api.moonshot.ai/v1',
    profiles: [
      {
        id: 'moonshot.default',
        label: '国际站',
        defaultApiBaseOpenai: 'https://api.moonshot.ai/v1',
      },
      {
        id: 'moonshot.cn',
        label: '国内站',
        defaultApiBaseOpenai: 'https://api.moonshot.cn/v1',
      },
      {
        id: 'moonshot.coding_plan',
        label: 'Kimi Code',
        defaultApiBaseOpenai: 'https://api.kimi.com/coding/v1',
      },
    ],
    availableScopes: SCOPES_ALL,
  },
  {
    id: 'volcengine',
    label: '火山引擎 (豆包/方舟)',
    apiBaseRequired: true,
    defaultApiBase: 'https://ark.cn-beijing.volces.com/api/v3',
    profiles: [
      {
        id: 'volcengine.standard',
        label: '方舟标准',
        defaultApiBaseOpenai: 'https://ark.cn-beijing.volces.com/api/v3',
      },
      {
        id: 'volcengine.coding_plan',
        label: 'Coding Plan',
        defaultApiBaseOpenai: 'https://ark.cn-beijing.volces.com/api/coding/v3',
        defaultApiBaseAnthropic: 'https://ark.cn-beijing.volces.com/api/coding',
        anthropicDirectHint:
          'Claude Code 直连 Anthropic 根为 /api/coding；经本 Gateway 代理时请使用 OpenAI-compat 根（已自动补 /v3）。',
      },
    ],
    availableScopes: SCOPES_ALL,
    extraFields: [
      {
        key: 'region',
        label: 'Region',
        type: 'select',
        options: VOLCENGINE_REGION_OPTIONS,
      },
      {
        key: 'endpoint_id',
        label: 'Endpoint ID（可选）',
        placeholder: 'ep-xxxxxxxxxxxxxxxx',
        type: 'text',
        helpText: '账户级 fallback；模型粒度更建议在模型注册中填写',
      },
    ],
  },
  {
    id: 'zhipuai',
    label: '智谱 AI (GLM)',
    apiBaseRequired: true,
    defaultApiBase: 'https://open.bigmodel.cn/api/paas/v4',
    profiles: [
      {
        id: 'zhipuai.standard',
        label: '标准 API',
        defaultApiBaseOpenai: 'https://open.bigmodel.cn/api/paas/v4',
      },
      {
        id: 'zhipuai.coding_plan',
        label: 'Coding Plan',
        defaultApiBaseOpenai: 'https://open.bigmodel.cn/api/coding/paas/v4',
      },
    ],
    availableScopes: SCOPES_ALL,
  },
  {
    id: 'agnes',
    label: 'Agnes AI (Sapiens)',
    defaultApiBase: 'https://apihub.agnes-ai.com/v1',
    availableScopes: SCOPES_ALL,
    helpText:
      'OpenAI 伪兼容端点：生图模型 agnes-image-2.x-flash 走 /v1/images/generations；图生图的输入图由 Gateway 自动封装为 extra_body。',
  },
  {
    id: 'cohere',
    label: 'Cohere',
    availableScopes: SCOPES_MANAGED,
  },
  {
    id: 'mistral',
    label: 'Mistral',
    defaultApiBase: 'https://api.mistral.ai/v1',
    availableScopes: SCOPES_MANAGED,
  },
  {
    id: 'fireworks',
    label: 'Fireworks AI',
    defaultApiBase: 'https://api.fireworks.ai/inference/v1',
    availableScopes: SCOPES_MANAGED,
  },
  {
    id: 'together_ai',
    label: 'Together AI',
    defaultApiBase: 'https://api.together.xyz/v1',
    availableScopes: SCOPES_MANAGED,
  },
]

const SCHEMA_BY_ID: ReadonlyMap<string, ProviderCredentialSchema> = new Map(
  PROVIDER_SCHEMAS.map((s) => [s.id, s])
)

export function getProviderSchema(providerId: string): ProviderCredentialSchema | undefined {
  return SCHEMA_BY_ID.get(providerId)
}

export function providersForScope(scope: CredentialFormScope): readonly ProviderCredentialSchema[] {
  return PROVIDER_SCHEMAS.filter((s) => {
    const scopes = s.availableScopes ?? SCOPES_ALL
    return scopes.includes(scope)
  })
}

export function profilesForProvider(providerId: string): readonly UpstreamProfileSpec[] {
  const remote = remoteProfilesForProvider(providerId)
  if (remote && remote.length > 0) {
    return remote
  }
  return SCHEMA_BY_ID.get(providerId)?.profiles ?? []
}

export function defaultProfileIdForProvider(providerId: string): string | undefined {
  const profiles = profilesForProvider(providerId)
  if (profiles.length === 0) return undefined
  const def = profiles.find((p) => p.id.endsWith('.default'))
  return def?.id ?? profiles[0]?.id
}

export function getUpstreamProfileSpec(
  providerId: string,
  profileId: string | undefined
): UpstreamProfileSpec | undefined {
  const profiles = profilesForProvider(providerId)
  if (profiles.length === 0) return undefined
  if (profileId) {
    const found = profiles.find((p) => p.id === profileId)
    if (found) return found
  }
  return profiles[0]
}

export function defaultApiBaseForProvider(providerId: string, profileId?: string): string {
  const spec = getUpstreamProfileSpec(providerId, profileId)
  if (spec?.defaultApiBaseOpenai) return spec.defaultApiBaseOpenai
  return SCHEMA_BY_ID.get(providerId)?.defaultApiBase ?? ''
}

export function providerLabel(providerId: string): string {
  return SCHEMA_BY_ID.get(providerId)?.label ?? providerId
}

export function extraFieldsForProvider(providerId: string): readonly CredentialFieldSpec[] {
  return SCHEMA_BY_ID.get(providerId)?.extraFields ?? []
}

export function apiKeyLabelForProvider(providerId: string): string {
  return SCHEMA_BY_ID.get(providerId)?.apiKeyLabel ?? 'API Key'
}
