/**
 * @see gateway-team-combobox.tsx
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'
import { GATEWAY_FILTER_ALL } from '@/features/gateway-usage/gateway-filter-combobox'

import { GatewayTeamCombobox } from './gateway-team-combobox'

const TEAM_A: GatewayTeam = {
  id: 'team-a',
  name: '研发',
  slug: 'rnd',
  kind: 'shared',
  owner_user_id: 'owner-1',
}

describe('GatewayTeamCombobox', () => {
  it('renders selected team label on trigger', () => {
    render(<GatewayTeamCombobox value="team-a" onChange={() => {}} teams={[TEAM_A]} />)

    expect(screen.getByText('研发')).toBeInTheDocument()
  })

  it('shows all-teams label when allowAll and value is GATEWAY_FILTER_ALL', () => {
    render(
      <GatewayTeamCombobox
        allowAll
        allLabel="全部团队"
        value={GATEWAY_FILTER_ALL}
        onChange={() => {}}
        teams={[TEAM_A]}
      />
    )

    expect(screen.getByRole('combobox')).toHaveTextContent('全部团队')
  })
})
