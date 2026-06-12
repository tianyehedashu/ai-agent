/**
 * 团队/系统凭据管理表格（系统 Tab 等 flat 列表）。
 */

import type React from 'react'

import type { GatewayCredentialUpdateBody, ProviderCredential } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { GatewayCredentialsPanelFallback } from '@/features/gateway-credentials/components/gateway-credentials-panel-fallback'
import { ManagedCredentialRow } from '@/features/gateway-credentials/managed-credential-row'
import { ManagedCredentialsTableHead } from '@/features/gateway-credentials/managed-credentials-table-head'
import type { CredentialsListTab } from '@/features/gateway-models/paths'
import { useGatewayTeamNameMap } from '@/features/gateway-teams/use-gateway-teams'

export interface ManagedCredentialsTableProps {
  items: ProviderCredential[] | undefined
  isLoading: boolean
  routeTeamId: string
  /** 空态行是否展示「新增」按钮（系统 Tab 已有工具栏时可关闭） */
  showEmptyAddButton?: boolean
  showAffiliationColumn: boolean
  viewerUserId: string | null | undefined
  canWrite: boolean
  isPlatformAdmin: boolean
  listVariant: 'team' | 'system'
  listTab?: CredentialsListTab
  emptyHint: string
  emptyState?: React.ReactNode
  toolbar?: React.ReactNode
  footer?: React.ReactNode
  /** 嵌入 ListShell 时不重复 Card 外壳 */
  embedded?: boolean
  onAdd: () => void
  onDelete: (c: ProviderCredential) => void
  updateMutation: {
    isPending: boolean
    mutate: (args: {
      id: string
      body: GatewayCredentialUpdateBody
      credentialTeamId: string
    }) => void
  }
}

export function ManagedCredentialsTable({
  items,
  isLoading,
  routeTeamId,
  showEmptyAddButton = true,
  showAffiliationColumn,
  viewerUserId,
  canWrite,
  isPlatformAdmin,
  listVariant,
  listTab,
  emptyHint,
  emptyState,
  toolbar,
  footer,
  embedded = false,
  onAdd,
  onDelete,
  updateMutation,
}: ManagedCredentialsTableProps): React.JSX.Element {
  const teamNameById = useGatewayTeamNameMap()
  const showAdd = canWrite || isPlatformAdmin
  const showAffiliation = showAffiliationColumn || listVariant === 'system'
  const colCount = showAffiliation ? 8 : 7
  const itemCount = items?.length ?? 0
  const isEmpty = !isLoading && itemCount === 0
  const showEmptyPanel = isEmpty && emptyState !== undefined
  const showLegacyEmptyRow = isEmpty && emptyState === undefined
  const showCenteredLoading = isLoading && itemCount === 0 && embedded
  const showTable = itemCount > 0 || showLegacyEmptyRow

  const tableBody = (
    <ScrollArea className="w-full overscroll-y-contain">
      <table className="w-full min-w-[720px] text-sm">
        <ManagedCredentialsTableHead
          layout="full"
          showAffiliationColumn={showAffiliationColumn}
          listVariant={listVariant}
        />
        <tbody>
          {isLoading && itemCount === 0 && !embedded ? (
            <tr>
              <td colSpan={colCount} className="px-4 py-6 text-center text-muted-foreground">
                加载中…
              </td>
            </tr>
          ) : null}
          {showLegacyEmptyRow ? (
            <tr>
              <td colSpan={colCount} className="px-4 py-8 text-center text-muted-foreground">
                <span className="mr-3">{emptyHint}</span>
                {showAdd && showEmptyAddButton ? (
                  <Button size="sm" variant="secondary" onClick={onAdd}>
                    新增
                  </Button>
                ) : null}
              </td>
            </tr>
          ) : null}
          {items?.map((c) => (
            <ManagedCredentialRow
              key={`${c.id}:${c.tenant_id ?? routeTeamId}`}
              credential={c}
              routeTeamId={routeTeamId}
              listVariant={listVariant}
              layout="full"
              showAffiliationColumn={showAffiliationColumn}
              teamNameById={teamNameById}
              viewerUserId={viewerUserId}
              canWrite={canWrite}
              isPlatformAdmin={isPlatformAdmin}
              listTab={listTab}
              onDelete={onDelete}
              updateMutation={updateMutation}
            />
          ))}
        </tbody>
      </table>
    </ScrollArea>
  )

  if (embedded) {
    if (showCenteredLoading) {
      return <GatewayCredentialsPanelFallback />
    }
    if (showEmptyPanel) {
      return <>{emptyState}</>
    }
    return showTable ? tableBody : <></>
  }

  return (
    <Card>
      {toolbar ? <div className="border-b p-3">{toolbar}</div> : null}
      <CardContent className="p-0">
        {showCenteredLoading ? <GatewayCredentialsPanelFallback /> : null}
        {showEmptyPanel ? <div className="p-4">{emptyState}</div> : null}
        {showTable && !showEmptyPanel ? tableBody : null}
      </CardContent>
      {footer ? <div className="border-t px-3 py-2">{footer}</div> : null}
    </Card>
  )
}
