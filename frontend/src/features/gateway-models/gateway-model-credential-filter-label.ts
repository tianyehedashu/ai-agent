import { channelLabel } from '@/features/gateway-models/utils'

export interface GatewayModelCredentialFilterOption {
  id: string
  name: string
  provider?: string
  teamLabel?: string
}

export function formatGatewayModelCredentialFilterLabel(
  option: GatewayModelCredentialFilterOption
): string {
  const base = option.provider ? `${option.name} · ${channelLabel(option.provider)}` : option.name
  if (option.teamLabel) {
    return `${option.teamLabel} · ${base}`
  }
  return base
}
