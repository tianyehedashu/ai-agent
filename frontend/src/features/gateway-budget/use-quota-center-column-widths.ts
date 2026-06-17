import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  buildQuotaCenterGridTemplateColumns,
  clampQuotaCenterColumnWidth,
  computeQuotaCenterTableMinWidth,
  type QuotaCenterColumnKey,
  type QuotaCenterColumnWidths,
} from '@/features/gateway-budget/quota-center-column-layout'
import {
  loadQuotaCenterColumnWidths,
  resetQuotaCenterColumnWidth,
  saveQuotaCenterColumnWidths,
} from '@/features/gateway-budget/quota-center-column-preferences'

interface ResizeDragState {
  key: QuotaCenterColumnKey
  startX: number
  startWidth: number
}

export interface UseQuotaCenterColumnWidthsResult {
  widths: QuotaCenterColumnWidths
  gridTemplateColumns: string
  tableMinWidth: number
  startResize: (key: QuotaCenterColumnKey, clientX: number) => void
  resetColumn: (key: QuotaCenterColumnKey) => void
}

export function useQuotaCenterColumnWidths(): UseQuotaCenterColumnWidthsResult {
  const [widths, setWidths] = useState<QuotaCenterColumnWidths>(loadQuotaCenterColumnWidths)
  const dragRef = useRef<ResizeDragState | null>(null)
  const widthsRef = useRef(widths)
  widthsRef.current = widths

  useEffect(() => {
    const onMove = (event: MouseEvent): void => {
      const drag = dragRef.current
      if (!drag) return
      const delta = event.clientX - drag.startX
      const nextWidth = clampQuotaCenterColumnWidth(drag.key, drag.startWidth + delta)
      setWidths((prev) =>
        prev[drag.key] === nextWidth ? prev : { ...prev, [drag.key]: nextWidth }
      )
    }

    const onUp = (): void => {
      if (!dragRef.current) return
      dragRef.current = null
      saveQuotaCenterColumnWidths(widthsRef.current)
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

  const startResize = useCallback((key: QuotaCenterColumnKey, clientX: number) => {
    dragRef.current = {
      key,
      startX: clientX,
      startWidth: widthsRef.current[key],
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  const resetColumn = useCallback((key: QuotaCenterColumnKey) => {
    setWidths((prev) => {
      const next = resetQuotaCenterColumnWidth(prev, key)
      saveQuotaCenterColumnWidths(next)
      return next
    })
  }, [])

  const gridTemplateColumns = useMemo(() => buildQuotaCenterGridTemplateColumns(widths), [widths])

  const tableMinWidth = useMemo(() => computeQuotaCenterTableMinWidth(widths), [widths])

  return {
    widths,
    gridTemplateColumns,
    tableMinWidth,
    startResize,
    resetColumn,
  }
}
