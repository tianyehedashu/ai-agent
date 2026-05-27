import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { GatewayTeamScopeBanner } from '@/features/gateway-teams/gateway-team-scope-banner'

vi.mock('@/features/gateway-teams/use-gateway-teams', () => ({
  useGatewayMemberTeams: () => ({
    data: [
      {
        id: 'team-personal',
        kind: 'personal' as const,
        name: 'Personal',
        owner_user_id: 'user-1',
      },
      {
        id: 'team-shared',
        kind: 'shared' as const,
        name: '研发',
        owner_user_id: 'user-1',
      },
    ],
  }),
}))

vi.mock('@/stores/user', () => ({
  useUserStore: (selector: (s: { currentUser: { id: string } | null }) => unknown) =>
    selector({ currentUser: { id: 'user-1' } }),
}))

describe('GatewayTeamScopeBanner', () => {
  it('personal 团队展示个人工作区文案', () => {
    render(
      <MemoryRouter>
        <GatewayTeamScopeBanner teamId="team-personal" variant="keys" />
      </MemoryRouter>
    )
    expect(screen.getByText(/仅解析本工作区已注册模型/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '模型管理' })).toHaveAttribute(
      'href',
      '/gateway/teams/team-personal/models'
    )
  })

  it('shared 团队说明 sk-gw 不读取 X-Team-Id', () => {
    render(
      <MemoryRouter>
        <GatewayTeamScopeBanner teamId="team-shared" variant="keys" />
      </MemoryRouter>
    )
    expect(screen.getByText('研发')).toBeInTheDocument()
    expect(screen.getByText(/不会读取 X-Team-Id/)).toBeInTheDocument()
  })
})
