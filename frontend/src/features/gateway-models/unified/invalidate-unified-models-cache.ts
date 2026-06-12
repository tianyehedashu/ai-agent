import type { QueryClient } from '@tanstack/react-query'

export const UNIFIED_MODELS_QUERY_KEY = ['gateway', 'unified-models'] as const

export function invalidateUnifiedModelsCache(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: UNIFIED_MODELS_QUERY_KEY })
}
