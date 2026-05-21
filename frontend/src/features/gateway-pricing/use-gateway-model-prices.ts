import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type MyPriceRow } from '@/api/gateway'
import { getCurrentTeamId } from '@/stores/gateway-team'
import type { DisplayCurrency } from '@/types/money'

export function useGatewayModelPrices(currency: DisplayCurrency): {
  byName: Map<string, MyPriceRow>
  isLoading: boolean
} {
  const teamId = getCurrentTeamId()
  const { data, isLoading } = useQuery({
    queryKey: ['gateway-pricing-my', teamId, currency],
    queryFn: () => {
      if (!teamId) return Promise.reject(new Error('未选择团队'))
      return gatewayApi.listMyPrices(teamId, { currency })
    },
    enabled: Boolean(teamId),
    staleTime: 60_000,
  })

  const byName = useMemo(() => {
    const map = new Map<string, MyPriceRow>()
    for (const row of data ?? []) {
      const key = row.model_name?.trim()
      if (key) map.set(key, row)
    }
    return map
  }, [data])

  return { byName, isLoading }
}
