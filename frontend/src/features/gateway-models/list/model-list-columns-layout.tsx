import { createContext, useContext, type ReactNode } from 'react'

import { useModelListColumnWidths } from './use-model-list-column-widths'

import type { ModelListColumnKey } from './model-list-column-layout'

interface ModelListColumnsLayoutContextValue {
  gridTemplateColumns: string
  tableMinWidth: number
  startResize: (key: ModelListColumnKey, clientX: number) => void
  resetColumn: (key: ModelListColumnKey) => void
}

const ModelListColumnsLayoutContext = createContext<ModelListColumnsLayoutContextValue | null>(null)

export interface ModelListColumnsLayoutProviderProps {
  showBatchSelect: boolean
  showTrailing: boolean
  showAffiliationColumn?: boolean
  children: ReactNode
}

export function ModelListColumnsLayoutProvider({
  showBatchSelect,
  showTrailing,
  showAffiliationColumn = true,
  children,
}: ModelListColumnsLayoutProviderProps): React.JSX.Element {
  const { gridTemplateColumns, tableMinWidth, startResize, resetColumn } = useModelListColumnWidths(
    {
      showBatchSelect,
      showTrailing,
      showAffiliationColumn,
    }
  )

  return (
    <ModelListColumnsLayoutContext.Provider
      value={{ gridTemplateColumns, tableMinWidth, startResize, resetColumn }}
    >
      {children}
    </ModelListColumnsLayoutContext.Provider>
  )
}

export function useModelListColumnsLayout(): ModelListColumnsLayoutContextValue {
  const ctx = useContext(ModelListColumnsLayoutContext)
  if (!ctx) {
    throw new Error('useModelListColumnsLayout must be used within ModelListColumnsLayoutProvider')
  }
  return ctx
}
