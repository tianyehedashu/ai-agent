/**
 * 系统 restricted 凭据在列表中的授权数量摘要（lazy query，react-query 缓存）。
 */

import type React from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'

function credentialGrantsQueryKey(credentialId: string): readonly string[] {
  return ['gateway', 'system-grants', 'credential', credentialId] as const
}

interface RestrictedCredentialGrantHintProps {
  credentialId: string
}

export function RestrictedCredentialGrantHint({
  credentialId,
}: RestrictedCredentialGrantHintProps): React.JSX.Element {
  const { data: grants = [], isLoading } = useQuery({
    queryKey: credentialGrantsQueryKey(credentialId),
    queryFn: () => gatewayApi.listCredentialGrants(credentialId),
  })

  const enabledCount = grants.filter((grant) => grant.enabled).length

  if (isLoading) {
    return <span className="text-[10px] text-muted-foreground">授权加载中…</span>
  }

  return (
    <span className="text-[10px] text-muted-foreground">
      {enabledCount > 0 ? `${String(enabledCount)} 个有效授权` : '暂无有效授权'}
    </span>
  )
}
