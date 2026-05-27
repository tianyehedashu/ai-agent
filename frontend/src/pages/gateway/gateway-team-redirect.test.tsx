import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { useGatewayTeamStore } from '@/stores/gateway-team'

import GatewayTeamRedirect from './gateway-team-redirect'

describe('GatewayTeamRedirect', () => {
  beforeEach(() => {
    useGatewayTeamStore.setState({
      teams: [
        {
          id: 'team-abc',
          name: '研发',
          slug: 'dev',
          kind: 'shared',
        },
      ],
    })
  })

  it('redirects legacy /gateway/stats to team stats workspace', () => {
    const router = createMemoryRouter(
      [
        { path: '/gateway/stats', element: <GatewayTeamRedirect /> },
        { path: '/gateway/teams/:teamId/stats', element: <div>stats workspace</div> },
      ],
      { initialEntries: ['/gateway/stats'] }
    )

    render(<RouterProvider router={router} />)
    expect(screen.getByText('stats workspace')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/gateway/teams/team-abc/stats')
  })

  it('redirects legacy /gateway/teams to members workspace', () => {
    const router = createMemoryRouter(
      [
        { path: '/gateway/teams', element: <GatewayTeamRedirect /> },
        { path: '/gateway/teams/:teamId/members', element: <div>members workspace</div> },
      ],
      { initialEntries: ['/gateway/teams'] }
    )

    render(<RouterProvider router={router} />)
    expect(screen.getByText('members workspace')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/gateway/teams/team-abc/members')
  })
})
