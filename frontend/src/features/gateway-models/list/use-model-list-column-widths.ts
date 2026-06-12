import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  buildModelListGridTemplateColumns,
  clampModelListColumnWidth,
  computeModelListTableMinWidth,
  type ModelListColumnKey,
  type ModelListColumnWidths,
  type ModelListGridOptions,
} from './model-list-column-layout'
import {
  loadModelListColumnWidths,
  resetModelListColumnWidth,
  saveModelListColumnWidths,
} from './model-list-column-preferences'

interface ResizeDragState {
  key: ModelListColumnKey
  startX: number
  startWidth: number
}

export interface UseModelListColumnWidthsResult {
  widths: ModelListColumnWidths
  gridTemplateColumns: string
  tableMinWidth: number
  startResize: (key: ModelListColumnKey, clientX: number) => void
  resetColumn: (key: ModelListColumnKey) => void
}

export function useModelListColumnWidths(
  gridOptions: ModelListGridOptions
): UseModelListColumnWidthsResult {
  const [widths, setWidths] = useState<ModelListColumnWidths>(loadModelListColumnWidths)
  const dragRef = useRef<ResizeDragState | null>(null)
  const widthsRef = useRef(widths)
  widthsRef.current = widths

  useEffect(() => {
    const onMove = (event: MouseEvent): void => {
      const drag = dragRef.current
      if (!drag) return
      const delta = event.clientX - drag.startX
      const nextWidth = clampModelListColumnWidth(drag.key, drag.startWidth + delta)
      setWidths((prev) =>
        prev[drag.key] === nextWidth ? prev : { ...prev, [drag.key]: nextWidth }
      )
    }

    const onUp = (): void => {
      if (!dragRef.current) return
      dragRef.current = null
      saveModelListColumnWidths(widthsRef.current)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [])

  const startResize = useCallback((key: ModelListColumnKey, clientX: number) => {
    dragRef.current = {
      key,
      startX: clientX,
      startWidth: widthsRef.current[key],
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  const resetColumn = useCallback((key: ModelListColumnKey) => {
    setWidths((prev) => {
      const next = resetModelListColumnWidth(prev, key)
      saveModelListColumnWidths(next)
      return next
    })
  }, [])

  const gridTemplateColumns = useMemo(
    () => buildModelListGridTemplateColumns(widths, gridOptions),
    [
      widths,
      gridOptions.showBatchSelect,
      gridOptions.showTrailing,
      gridOptions.showAffiliationColumn,
    ]
  )

  const tableMinWidth = useMemo(
    () => computeModelListTableMinWidth(widths, gridOptions),
    [
      widths,
      gridOptions.showBatchSelect,
      gridOptions.showTrailing,
      gridOptions.showAffiliationColumn,
    ]
  )

  return {
    widths,
    gridTemplateColumns,
    tableMinWidth,
    startResize,
    resetColumn,
  }
}
