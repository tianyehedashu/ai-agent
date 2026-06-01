import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { UsageStatsBreakdownCredentials } from './usage-stats-breakdown-credentials'
import { UsageStatsBreakdownPrimary } from './usage-stats-breakdown-primary'
import { getUsageStatsIdentityColumnHeaders } from './usage-stats-group-options'

describe('getUsageStatsIdentityColumnHeaders', () => {
  it('returns 人员 | 模型 | 凭据 for user grouping', () => {
    expect(getUsageStatsIdentityColumnHeaders('user')).toEqual(['人员', '模型', '凭据'])
  })

  it('keeps model and credential labels for team grouping', () => {
    expect(getUsageStatsIdentityColumnHeaders('team')).toEqual(['团队', '模型', '凭据'])
  })
})

describe('UsageStatsBreakdownPrimary', () => {
  it('renders only the first slice', () => {
    render(
      <UsageStatsBreakdownPrimary
        data={{
          parent_group_by: 'user',
          parent_group_key: 'u1',
          breakdown_by: 'model',
          parent_requests: 10,
          items: [
            { group_key: 'm1', label: 'glm-4', requests: 6, share: 0.6 },
            { group_key: 'm2', label: 'gpt-4', requests: 4, share: 0.4 },
          ],
        }}
      />
    )
    expect(screen.getByText('glm-4')).toBeInTheDocument()
    expect(screen.queryByText('gpt-4')).not.toBeInTheDocument()
    expect(screen.queryByText(/#1/)).not.toBeInTheDocument()
  })
})

describe('UsageStatsBreakdownCredentials', () => {
  it('renders stacked bar with top1 label and overflow count, no rank labels', () => {
    render(
      <UsageStatsBreakdownCredentials
        data={{
          parent_group_by: 'user',
          parent_group_key: 'u1',
          breakdown_by: 'credential',
          parent_requests: 10,
          items: [
            { group_key: 'c1', label: '火山-company', requests: 6, share: 0.6 },
            { group_key: 'c2', label: '火山-personal', requests: 4, share: 0.4 },
          ],
        }}
      />
    )
    // 顶部条按 group_key 渲染每个分片（次要凭据名仅出现在 title 中）。
    expect(screen.getByTitle(/火山-personal/)).toBeInTheDocument()
    // 摘要行只展示 Top1 凭据名 + 占比 + 溢出计数。
    expect(screen.getByText('火山-company')).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
    expect(screen.getByText('+1')).toBeInTheDocument()
    expect(screen.queryByText(/#1/)).not.toBeInTheDocument()
  })

  it('shows unassigned-request hint when parent exceeds listed slices', () => {
    render(
      <UsageStatsBreakdownCredentials
        data={{
          parent_group_by: 'user',
          parent_group_key: 'u1',
          breakdown_by: 'credential',
          parent_requests: 10,
          items: [{ group_key: 'c1', label: '火山-company', requests: 6, share: 0.6 }],
        }}
      />
    )
    expect(screen.getByText(/4 次请求未关联凭据/)).toBeInTheDocument()
  })
})
