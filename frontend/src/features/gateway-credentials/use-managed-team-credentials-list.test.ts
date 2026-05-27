/**
 * useManagedTeamCredentialsList 行为单测
 */

import React from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import type {
  ListManagedTeamCredentialsParams,
  ManagedTeamCredentialListResponse,
} from '@/api/gateway/credentials'

import { useManagedTeamCredentialsList } from './use-managed-team-credentials-list'

const emptyManagedTeamCredentialListResponse = (): ManagedTeamCredentialListResponse => ({
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  has_next: false,
  has_prev: false,
  queried_team_count: 0,
  queried_personal_team_count: 0,
  queried_shared_team_count: 0,
  tenant_ids_with_credentials: [],
})

const listManagedTeamCredentialsMock = vi.fn(
  (_params?: ListManagedTeamCredentialsParams): Promise<ManagedTeamCredentialListResponse> =>
    Promise.resolve(emptyManagedTeamCredentialListResponse())
)

vi.mock('@/api/gateway/credentials', () => ({
  credentialsApi: {
    listManagedTeamCredentials: listManagedTeamCredentialsMock,
  },
}))

function wrapper(): React.FC<{ children: React.ReactNode }> {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }) => React.createElement(QueryClientProvider, { client: qc }, children)
}

beforeEach(() => {
  listManagedTeamCredentialsMock.mockClear()
  listManagedTeamCredentialsMock.mockResolvedValue(emptyManagedTeamCredentialListResponse())
})

describe('useManagedTeamCredentialsList', () => {
  test('enabled=false 时不请求', () => {
    renderHook(
      () =>
        useManagedTeamCredentialsList({
          search: '',
          page: 1,
          enabled: false,
        }),
      { wrapper: wrapper() }
    )
    expect(listManagedTeamCredentialsMock).not.toHaveBeenCalled()
  })

  test('trim 空白 search 并传递 page/page_size', async () => {
    renderHook(
      () =>
        useManagedTeamCredentialsList({
          search: '  ',
          page: 2,
          pageSize: 10,
          enabled: true,
        }),
      { wrapper: wrapper() }
    )

    await waitFor(() => {
      expect(listManagedTeamCredentialsMock).toHaveBeenCalledWith({
        search: undefined,
        page: 2,
        page_size: 10,
      })
    })
  })

  test('保留非空 search', async () => {
    renderHook(
      () =>
        useManagedTeamCredentialsList({
          search: '  alpha  ',
          page: 1,
          enabled: true,
        }),
      { wrapper: wrapper() }
    )

    await waitFor(() => {
      expect(listManagedTeamCredentialsMock).toHaveBeenCalledWith({
        search: 'alpha',
        page: 1,
        page_size: 20,
      })
    })
  })
})
