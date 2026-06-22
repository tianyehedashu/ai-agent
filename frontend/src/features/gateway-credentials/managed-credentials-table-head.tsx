import type React from 'react'

export type ManagedCredentialsTableLayout = 'full' | 'compact'

export interface ManagedCredentialsTableHeadProps {
  layout: ManagedCredentialsTableLayout
  showAffiliationColumn?: boolean
  listVariant?: 'team' | 'system'
}

export function ManagedCredentialsTableHead({
  layout,
  showAffiliationColumn = false,
  listVariant = 'team',
}: ManagedCredentialsTableHeadProps): React.JSX.Element {
  const showAffiliation = showAffiliationColumn || listVariant === 'system'

  if (layout === 'compact') {
    const showAffiliation = showAffiliationColumn || listVariant === 'system'
    return (
      <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
        <tr>
          <th className="px-4 py-2 text-left font-medium">名称</th>
          <th className="px-4 py-2 text-left font-medium">API Key</th>
          <th className="px-4 py-2 text-left font-medium">提供商</th>
          {showAffiliation ? <th className="px-4 py-2 text-left font-medium">归属</th> : null}
          <th className="px-4 py-2 text-left font-medium">提供者</th>
          <th className="px-4 py-2 text-left font-medium">启用</th>
          <th className="px-4 py-2 text-left font-medium">操作</th>
        </tr>
      </thead>
    )
  }

  return (
    <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
      <tr>
        <th className="px-4 py-2 text-left font-medium">名称</th>
        <th className="px-4 py-2 text-left font-medium">API Key</th>
        <th className="px-4 py-2 text-left font-medium">提供商</th>
        <th className="px-4 py-2 text-left font-medium">作用域</th>
        {showAffiliation ? <th className="px-4 py-2 text-left font-medium">归属</th> : null}
        <th className="px-4 py-2 text-left font-medium">提供者</th>
        <th className="px-4 py-2 text-left font-medium">api_base</th>
        <th className="px-4 py-2 text-left font-medium">启用</th>
        <th className="px-4 py-2 text-left font-medium">操作</th>
      </tr>
    </thead>
  )
}
