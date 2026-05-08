/**
 * Video Settings Store
 *
 * 管理视频生成相关的用户偏好设置，使用 Zustand persist 持久化。
 *
 * 用户隔离策略：
 * - 通过 `userPrompts` Record 按用户标识存储，同一浏览器多账号互不干扰
 * - 用户标识来自 authStore（token 对应的用户或 anonymousUserId）
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

const STORAGE_KEY = 'video-settings-storage'

interface VideoSettingsState {
  /** 按用户标识存储自定义系统提示词（key = userId/anonymousId） */
  userPrompts: Record<string, string>

  /** 获取当前用户的系统提示词（空字符串表示使用默认） */
  getSystemPrompt: (userKey: string) => string

  /** 设置当前用户的系统提示词 */
  setSystemPrompt: (userKey: string, prompt: string) => void

  /** 清除当前用户的自定义系统提示词（恢复默认） */
  clearSystemPrompt: (userKey: string) => void
}

export const useVideoSettingsStore = create<VideoSettingsState>()(
  persist(
    (set, get) => ({
      userPrompts: {},

      getSystemPrompt: (userKey) => {
        return get().userPrompts[userKey] ?? ''
      },

      setSystemPrompt: (userKey, prompt) => {
        set((state) => ({
          userPrompts: { ...state.userPrompts, [userKey]: prompt },
        }))
      },

      clearSystemPrompt: (userKey) => {
        set((state) => {
          const { [userKey]: _, ...rest } = state.userPrompts
          return { userPrompts: rest }
        })
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        userPrompts: state.userPrompts,
      }),
    }
  )
)
