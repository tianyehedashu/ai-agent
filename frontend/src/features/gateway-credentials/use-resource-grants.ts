import { useMutation, useQueryClient } from '@tanstack/react-query'

import { resourceGrantsApi, type ResourceGrantCreateBody } from '@/api/gateway/resource-grants'

export const RESOURCE_GRANTS_QUERY_KEY = ['gateway', 'resource-grants'] as const

export function useGrantResourceToTeams() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ResourceGrantCreateBody) => resourceGrantsApi.create(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: RESOURCE_GRANTS_QUERY_KEY })
      void qc.invalidateQueries({ queryKey: ['gateway'] })
    },
  })
}
