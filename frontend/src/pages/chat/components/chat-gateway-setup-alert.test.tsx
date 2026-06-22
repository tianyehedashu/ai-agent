import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test } from 'vitest'

import {
  ChatGatewaySetupAlert,
  isChatReadinessLoading,
  isChatReady,
} from './chat-gateway-setup-alert'

test('isChatReady only true when readiness is ready', () => {
  expect(isChatReady('ready')).toBe(true)
  expect(isChatReady(undefined)).toBe(false)
  expect(isChatReady('needs_credential')).toBe(false)
})

test('isChatReadinessLoading when models not loaded', () => {
  expect(isChatReadinessLoading(undefined, false)).toBe(true)
  expect(isChatReadinessLoading(undefined, true)).toBe(false)
  expect(isChatReadinessLoading('needs_model', false)).toBe(false)
})

test('does not show alert while models are loading', () => {
  const { container } = render(
    <ChatGatewaySetupAlert readiness={undefined} workspaceTeamId="team-1" modelsLoaded={false} />
  )
  expect(container).toBeEmptyDOMElement()
})

test('shows credential alert when loaded and needs credential', () => {
  render(
    <MemoryRouter>
      <ChatGatewaySetupAlert readiness="needs_credential" workspaceTeamId="team-1" modelsLoaded />
    </MemoryRouter>
  )
  expect(screen.getByText('无法开始对话')).toBeInTheDocument()
})
