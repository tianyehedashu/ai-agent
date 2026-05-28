/**
 * @see gateway-team-combobox.tsx
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'

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
})
