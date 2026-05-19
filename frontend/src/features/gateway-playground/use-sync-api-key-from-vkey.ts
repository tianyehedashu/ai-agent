/**
 * 把试调虚拟 Key 的明文同步到 apiKey 输入框。
 *
 * 行为：
 * - 用户手动编辑过（`userEditedRef.current === true`）时一切不动，保留手动粘贴值
 * - 选中的 Key 已 reveal 出明文 `plain` → 写入 `apiKey`
 * - 显式取消选择（`selectedKeyId === null`）→ 清空 `apiKey`，避免残留上一把 Key 的明文
 * - 选中但仍在 reveal 中（plain 暂为 null、selectedKeyId 非 null）→ 不改动，等待明文到达
 */

import { useEffect } from 'react'
import type { RefObject } from 'react'

export interface SyncApiKeyFromVkeyOptions {
  plain: string | null
  selectedKeyId: string | null
  userEditedRef: RefObject<boolean>
  setApiKey: (value: string) => void
}

export function useSyncApiKeyFromVkey({
  plain,
  selectedKeyId,
  userEditedRef,
  setApiKey,
}: SyncApiKeyFromVkeyOptions): void {
  useEffect(() => {
    if (userEditedRef.current) return
    if (plain) {
      setApiKey(plain)
    } else if (selectedKeyId === null) {
      setApiKey('')
    }
    // setApiKey 来自 useState 稳定；userEditedRef 是 ref；故依赖 plain + selectedKeyId 即可
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 见上注释
  }, [plain, selectedKeyId])
}
