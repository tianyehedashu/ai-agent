/**
 * Gateway Team Store
 *
 * 管理当前选中的 AI Gateway 团队上下文。
 * - 持久化到 localStorage
 * - axios interceptor 会读取 currentTeamId 注入 X-Team-Id header
 * - 切换 team 时调用方应该 invalidate ['gateway'] 相关查询
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export interface GatewayTeam {
  id: string
  name: string
  slug: string
  kind: 'personal' | 'shared'
  team_role?: string | null
}

interface GatewayTeamState {
  teams: GatewayTeam[]
  currentTeamId: string | null
  setTeams: (teams: GatewayTeam[]) => void
  setCurrentTeamId: (teamId: string | null) => void
  clear: () => void
  /** 当前 team 对象 */
  current: () => GatewayTeam | null
}

const STORAGE_KEY = 'gateway-team-storage'

export const useGatewayTeamStore = create<GatewayTeamState>()(
  persist(
    (set, get) => ({
      teams: [],
      currentTeamId: null,
      setTeams: (teams) => {
        const { currentTeamId } = get()
        // 保留当前选中（若仍在列表中），否则默认选 personal team
        const stillExists = currentTeamId && teams.some((t) => t.id === currentTeamId)
        const preferred =
          teams.length > 0 ? (teams.find((t) => t.kind === 'personal') ?? teams[0]) : undefined
        set({
          teams,
          currentTeamId: stillExists ? currentTeamId : (preferred?.id ?? null),
        })
      },
      setCurrentTeamId: (teamId) => {
        set({ currentTeamId: teamId })
      },
      clear: () => {
        set({ teams: [], currentTeamId: null })
      },
      current: () => {
        const { teams, currentTeamId } = get()
        return teams.find((t) => t.id === currentTeamId) ?? null
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        currentTeamId: state.currentTeamId,
        teams: state.teams,
      }),
    }
  )
)

export const getCurrentTeamId = (): string | null => useGatewayTeamStore.getState().currentTeamId
