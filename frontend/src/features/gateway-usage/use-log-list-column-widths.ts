import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  buildLogGridTemplateColumns,
  clampLogListColumnWidth,
  computeLogTableMinWidth,
  type LogListColumnWidths,
  type LogListGridOptions,
  type LogListColumnKey,
} from '@/features/gateway-usage/log-list-column-layout'
import {
  loadLogListColumnWidths,
  resetLogListColumnWidth,
  saveLogListColumnWidths,
} from '@/features/gateway-usage/log-list-column-preferences'

interface ResizeDragState {
  key: LogListColumnKey
  startX: number
  startWidth: number
}

export interface UseLogListColumnWidthsResult {
  widths: LogListColumnWidths
  gridTemplateColumns: string
  tableMinWidth: number
  startResize: (key: LogListColumnKey, clientX: number) => void
  resetColumn: (key: LogListColumnKey) => void
}

export function useLogListColumnWidths(
  gridOptions: LogListGridOptions
): UseLogListColumnWidthsResult {
  const [widths, setWidths] = useState<LogListColumnWidths>(loadLogListColumnWidths)
  const dragRef = useRef<ResizeDragState | null>(null)
  const widthsRef = useRef(widths)
  widthsRef.current = widths

  useEffect(() => {
    const onMove = (event: MouseEvent): void => {
      const drag = dragRef.current
      if (!drag) return
      const delta = event.clientX - drag.startX
      const nextWidth = clampLogListColumnWidth(drag.key, drag.startWidth + delta)
      setWidths((prev) =>
        prev[drag.key] === nextWidth ? prev : { ...prev, [drag.key]: nextWidth }
      )
    }

    const onUp = (): void => {
      if (!dragRef.current) return
      dragRef.current = null
      saveLogListColumnWidths(widthsRef.current)
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

  const startResize = useCallback((key: LogListColumnKey, clientX: number) => {
    dragRef.current = {
      key,
      startX: clientX,
      startWidth: widthsRef.current[key],
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  const resetColumn = useCallback((key: LogListColumnKey) => {
    setWidths((prev) => {
      const next = resetLogListColumnWidth(prev, key)
      saveLogListColumnWidths(next)
      return next
    })
  }, [])

  const gridTemplateColumns = useMemo(
    () => buildLogGridTemplateColumns(gridOptions, widths),
    [gridOptions.showCallerColumn, widths]
  )

  const tableMinWidth = useMemo(
    () => computeLogTableMinWidth(gridOptions, widths),
    [gridOptions.showCallerColumn, widths]
  )

  return {
    widths,
    gridTemplateColumns,
    tableMinWidth,
    startResize,
    resetColumn,
  }
}
