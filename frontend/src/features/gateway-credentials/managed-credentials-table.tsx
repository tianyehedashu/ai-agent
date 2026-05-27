/**
 * 团队/系统凭据管理表格（系统 Tab 等 flat 列表）。
 */

import type React from 'react'

import type { GatewayCredentialUpdateBody, ProviderCredential } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ManagedCredentialRow } from '@/features/gateway-credentials/managed-credential-row'

export interface ManagedCredentialsTableProps {
  items: ProviderCredential[] | undefined
  isLoading: boolean
  routeTeamId: string
  /** 空态行是否展示「新增」按钮（系统 Tab 已有工具栏时可关闭） */
  showEmptyAddButton?: boolean
  showAffiliationColumn: boolean
  canWrite: boolean
  isAdmin: boolean
  isPlatformAdmin: boolean
  listVariant: 'team' | 'system'
  emptyHint: string
  emptyState?: React.ReactNode
  toolbar?: React.ReactNode
  footer?: React.ReactNode
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
  canWrite,
  isAdmin,
  isPlatformAdmin,
  listVariant,
  emptyHint,
  emptyState,
  toolbar,
  footer,
  onAdd,
  onDelete,
  updateMutation,
}: ManagedCredentialsTableProps): React.JSX.Element {
  const showAdd = canWrite || isPlatformAdmin
  const showAffiliation = showAffiliationColumn || listVariant === 'system'
  const colCount = showAffiliation ? 8 : 7
  const itemCount = items?.length ?? 0
  const isEmpty = !isLoading && itemCount === 0
  const showEmptyPanel = isEmpty && emptyState !== undefined
  const showLegacyEmptyRow = isEmpty && emptyState === undefined
  const showCenteredLoading = isLoading && itemCount === 0 && emptyState !== undefined
  const showTable = itemCount > 0 || showLegacyEmptyRow

  return (
    <Card>
      {toolbar ? <div className="border-b p-3">{toolbar}</div> : null}
      <CardContent className="p-0">
        {showCenteredLoading ? (
          <div className="px-4 py-12 text-center text-sm text-muted-foreground">加载中…</div>
        ) : null}
        {showEmptyPanel ? <div className="p-4">{emptyState}</div> : null}
        {showTable && !showEmptyPanel ? (
          <ScrollArea className="w-full overscroll-y-contain">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">名称</th>
                  <th className="px-4 py-2 text-left font-medium">API Key</th>
                  <th className="px-4 py-2 text-left font-medium">提供商</th>
                  <th className="px-4 py-2 text-left font-medium">作用域</th>
                  {showAffiliation ? (
                    <th className="px-4 py-2 text-left font-medium">归属</th>
                  ) : null}
                  <th className="px-4 py-2 text-left font-medium">api_base</th>
                  <th className="px-4 py-2 text-left font-medium">启用</th>
                  <th className="px-4 py-2 text-left font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {isLoading && itemCount === 0 ? (
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
                    showAffiliationColumn={showAffiliationColumn}
                    canWrite={canWrite}
                    isAdmin={isAdmin}
                    isPlatformAdmin={isPlatformAdmin}
                    onDelete={onDelete}
                    updateMutation={updateMutation}
                  />
                ))}
              </tbody>
            </table>
          </ScrollArea>
        ) : null}
      </CardContent>
      {footer ? <div className="border-t px-3 py-2">{footer}</div> : null}
    </Card>
  )
}
