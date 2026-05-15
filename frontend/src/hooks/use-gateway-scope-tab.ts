import { useSearchParams } from 'react-router-dom'

import { type ModelScopeTab, parseScopeTab } from '@/features/gateway-models/constants'

export function useGatewayScopeTab(): ModelScopeTab {
  const [searchParams] = useSearchParams()
  return parseScopeTab(searchParams.get('tab'))
}
