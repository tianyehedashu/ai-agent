/**
 * AI Gateway · 虚拟 Key 管理
 */

import { GatewayKeysWorkspace } from '@/features/gateway-keys/keys-workspace'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'

export default function GatewayKeysPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  return <GatewayKeysWorkspace teamId={teamId} />
}
