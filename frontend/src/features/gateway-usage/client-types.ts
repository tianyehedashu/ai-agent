/**
 * Gateway 调用日志 client_type 常量
 *
 * 与 backend ``gateway_request_logs.client_type`` 对齐。
 * 新增 client_type 时应同步更新此文件与后端 CustomLogger/metadata 写入点。
 */

export const GATEWAY_CLIENT_TYPES = {
  /** 普通调用（未显式设置 client_type 时的兜底） */
  UNKNOWN: 'unknown',
  /** 模型连通性探活 */
  MODEL_CONNECTIVITY_PROBE: 'model_connectivity_probe',
} as const

export type GatewayClientType = (typeof GATEWAY_CLIENT_TYPES)[keyof typeof GATEWAY_CLIENT_TYPES]

export function isGatewayClientType(value: string): value is GatewayClientType {
  return Object.values(GATEWAY_CLIENT_TYPES).includes(value as GatewayClientType)
}
