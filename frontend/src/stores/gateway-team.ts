/**
 * Gateway Team Store
 *
 * 缓存 membership 团队列表（供标签解析、personal 工作区回退等）。
 * 团队上下文 SSOT 为 URL `/gateway/teams/:teamId/*`；扁平路由用 personal team。
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
  setTeams: (teams: GatewayTeam[]) => void
  clear: () => void
}

const STORAGE_KEY = 'gateway-team-storage'

export const useGatewayTeamStore = create<GatewayTeamState>()(
  persist(
    (set) => ({
      teams: [],
      setTeams: (teams) => {
        set({ teams })
      },
      clear: () => {
        set({ teams: [] })
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ teams: state.teams }),
    }
  )
)
