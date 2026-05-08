/**
 * Product Info Store
 *
 * 管理产品信息页面需要跨刷新持久化的草稿状态。
 *
 * 持久化字段：
 * - lastJobId: 最近活跃的任务 ID（用于无 URL 参数时自动恢复）
 * - draftInputs: 用户输入表单草稿（产品链接、关键词等）
 *
 * @example
 * ```tsx
 * const lastJobId = useProductInfoStore((s) => s.lastJobId)
 * const draftInputs = useProductInfoStore((s) => s.draftInputs)
 * const { setLastJobId, setDraftInputs } = useProductInfoStore.getState()
 * ```
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface ProductInfoInputs {
  product_link?: string
  competitor_link?: string
  product_name?: string
  keywords?: string
  image_urls?: string[]
}

interface ProductInfoState {
  lastJobId: string | null
  draftInputs: ProductInfoInputs

  setLastJobId: (id: string | null) => void
  setDraftInputs: (inputs: ProductInfoInputs) => void
}

export const useProductInfoStore = create<ProductInfoState>()(
  persist(
    (set) => ({
      lastJobId: null,
      draftInputs: {},

      setLastJobId: (id) => {
        set({ lastJobId: id })
      },
      setDraftInputs: (inputs) => {
        set({ draftInputs: inputs })
      },
    }),
    {
      name: 'product-info-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        lastJobId: state.lastJobId,
        draftInputs: state.draftInputs,
      }),
    }
  )
)

export const getLastJobId = (): string | null => useProductInfoStore.getState().lastJobId

export const setLastJobId = (id: string | null): void => {
  useProductInfoStore.getState().setLastJobId(id)
}
