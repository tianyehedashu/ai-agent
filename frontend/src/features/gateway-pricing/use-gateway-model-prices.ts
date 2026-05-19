import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type MyPriceRow } from '@/api/gateway'
import type { DisplayCurrency } from '@/types/money'

export function useGatewayModelPrices(currency: DisplayCurrency): {
  byName: Map<string, MyPriceRow>
  isLoading: boolean
} {
  const { data, isLoading } = useQuery({
    queryKey: ['gateway-pricing-my', currency],
    queryFn: () => gatewayApi.listMyPrices({ currency }),
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
