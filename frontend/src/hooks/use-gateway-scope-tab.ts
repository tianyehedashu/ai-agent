import { useCallback, useEffect } from 'react'

import { useSearchParams } from 'react-router-dom'

import {
  type GatewayScopeTab,
  isGatewayScopeTabValue,
  parseScopeTab,
} from '@/features/gateway-models/constants'

export interface UseGatewayScopeTabOptions {
  /** 平台管理员可使用 `?tab=system` */
  allowSystemTab?: boolean
  /** 写入 URL 前调用（如关闭弹窗） */
  onBeforeTabChange?: () => void
  /** 切换 tab 时对 URLSearchParams 的额外修改 */
  mutateParamsOnTabChange?: (next: GatewayScopeTab, params: URLSearchParams) => void
  /** 旧 `?tab=team` 等迁移时对 URLSearchParams 的额外修改 */
  mutateParamsOnLegacyMigrate?: (params: URLSearchParams) => void
}

export interface UseGatewayScopeTabResult {
  scopeTab: GatewayScopeTab
  setScopeTab: (next: GatewayScopeTab) => void
  searchParams: URLSearchParams
  setSearchParams: ReturnType<typeof useSearchParams>[1]
}

/**
 * 解析并同步 `?tab=personal|shared`（兼容 `team` → `shared`），
 * 在首屏将非法 tab 重写为 `shared`。
 */
export function useGatewayScopeTab(
  options: UseGatewayScopeTabOptions = {}
): UseGatewayScopeTabResult {
  const {
    allowSystemTab = false,
    onBeforeTabChange,
    mutateParamsOnTabChange,
    mutateParamsOnLegacyMigrate,
  } = options
  const parseOptions = { allowSystem: allowSystemTab }
  const [searchParams, setSearchParams] = useSearchParams()
  const scopeTab = parseScopeTab(searchParams.get('tab'), parseOptions)

  useEffect(() => {
    const raw = searchParams.get('tab')
    if (raw !== null && !isGatewayScopeTabValue(raw, { allowSystem: allowSystemTab })) {
      onBeforeTabChange?.()
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('tab', 'shared')
          mutateParamsOnLegacyMigrate?.(n)
          return n
        },
        { replace: true }
      )
    }
  }, [
    searchParams,
    setSearchParams,
    onBeforeTabChange,
    mutateParamsOnLegacyMigrate,
    allowSystemTab,
  ])

  const setScopeTab = useCallback(
    (next: GatewayScopeTab): void => {
      onBeforeTabChange?.()
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('tab', next)
          mutateParamsOnTabChange?.(next, n)
          return n
        },
        { replace: true }
      )
    },
    [setSearchParams, onBeforeTabChange, mutateParamsOnTabChange]
  )

  return { scopeTab, setScopeTab, searchParams, setSearchParams }
}
