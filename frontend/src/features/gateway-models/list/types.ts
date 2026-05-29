import type { ReactNode } from 'react'

import type { GatewayModel, GatewayModelRouteUsageItem } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'
import type { GatewayTeam } from '@/api/gateway/teams'
import type { HealthFilter, UsagePeriodDays } from '@/features/gateway-models/constants'
import type { ModelWithConnectivityStatus } from '@/features/gateway-models/utils'
import type { ModelTestStatus } from '@/types/user-model'

/** 列表数据来源作用域 */
export type GatewayModelListScope = 'personal' | 'team' | 'system'

export type EntitlementStatus = 'active' | 'exhausted' | 'resetting' | 'expired' | 'none'

export type GatewayModelListVariant = 'default' | 'readonly' | 'embedded'

export type BatchBarMode = 'onSelection' | 'whenHasItems'

export type DeleteAllFilteredFetcher = 'personal' | 'managed-teams' | 'single-team'

export type GatewayModelListLayout = 'stacked' | 'compact'

export type ConnectivityDisplay = 'always' | 'attention-only'

/** 列表 preset 能力开关（Shell / Toolbar / Row / BatchBar 统一裁剪） */
export interface GatewayModelListCapabilities {
  scope: GatewayModelListScope
  variant?: GatewayModelListVariant
  search?: boolean
  credentialFilter?: boolean
  channelFilter?: boolean
  abilityFilter?: boolean
  healthFilter?: boolean
  credentialBanner?: boolean
  modelIdHighlight?: boolean
  channelHint?: boolean
  usageSummary?: boolean
  batchSelect?: boolean
  batchBarMode?: BatchBarMode
  batchTest?: boolean
  batchResync?: boolean
  batchDelete?: boolean
  deleteAllFiltered?: boolean
  deleteAllFilteredFetcher?: DeleteAllFilteredFetcher
  deleteFailed?: boolean
  rowToggleEnabled?: boolean
  rowDelete?: boolean
  rowNavigation?: boolean
  connectivityBanner?: boolean
  layout?: GatewayModelListLayout
  connectivityDisplay?: ConnectivityDisplay
  groupedByTeam?: boolean
  teamSearch?: boolean
  dualSearchStaleLoading?: boolean
  showSystemAdmin?: boolean
  headerSlot?: boolean
}

/** 统一列表行 ViewModel */
export interface GatewayModelListItem {
  id: string
  scope: GatewayModelListScope
  /** personal: display_name；其它: name */
  title: string
  /** personal 第二行 mono（PersonalGatewayModel.name） */
  routeName?: string
  /** 通道 · 上游 ID */
  subtitle: string
  /** personal: model_id；其它: real_model */
  upstreamModelId: string
  provider: string
  capability: string
  modelTypes: string[]
  selectorCapabilities?: Record<string, unknown>
  /** personal: is_active；其它: enabled */
  enabled: boolean
  lastTestStatus: ModelTestStatus
  lastTestedAt: string | null
  lastTestReason: string | null
  entitlementStatus?: EntitlementStatus
  entitlementResetAt?: string | null
  teamId?: string | null
  registryKind?: 'team' | 'system'
  source: PersonalGatewayModel | GatewayModel
}

/** Shell 权限裁剪输入 */
export interface GatewayModelListPermissionContext {
  /** 团队 admin+（含 legacy 共享凭据/跨筛选批量等管理面写权限） */
  canWrite: boolean
  /**
   * 团队 member+（创建者私有）：可对自有模型行级启停/删除、批量勾选删除自有模型。
   * 缺省回退到 `canWrite` 以兼容仅管理员场景；具体行级归属仍由 Row callback 裁剪。
   */
  canContribute?: boolean
  isPlatformAdmin: boolean
}

/** Row 级权限 gate（由 Workspace 注入） */
export interface GatewayModelListRowPermissions {
  canManage?: (item: GatewayModelListItem) => boolean
  canDelete?: (item: GatewayModelListItem) => boolean
  canBatchSelect?: (item: GatewayModelListItem) => boolean
  isConfigManaged?: (item: GatewayModelListItem) => boolean
}

export interface GatewayModelListRowProps extends GatewayModelListRowPermissions {
  item: GatewayModelListItem
  capabilities: GatewayModelListCapabilities
  selected?: boolean
  highlighted?: boolean
  usageDays?: UsagePeriodDays
  usageRow?: GatewayModelRouteUsageItem
  usageLoading?: boolean
  href?: string
  onSelect?: (id: string) => void
  onPreloadNavigate?: () => void
  batchSelected?: boolean
  onBatchSelectChange?: (id: string, selected: boolean) => void
  isDeleting?: boolean
  onDelete?: (id: string) => void
  trailingActions?: ReactNode
}

export interface GatewayModelListToolbarProps {
  capabilities: GatewayModelListCapabilities
  search: string
  onSearchChange: (value: string) => void
  providerFilter: string
  onProviderFilterChange: (value: string) => void
  abilityFilter: string
  onAbilityFilterChange: (value: string) => void
  credentialFilter?: string
  onCredentialFilterChange?: (value: string) => void
  credentialFilterOptions?: readonly {
    id: string
    name: string
    provider?: string
    tenant_id?: string
  }[]
  credentialFilterLoading?: boolean
  selectedCredentialName?: string | null
  providerChoices: readonly string[]
  healthFilter: HealthFilter
  onHealthFilterChange: (filter: HealthFilter) => void
  connectivitySummary?: {
    total: number
    success: number
    failed: number
    unknown: number
  }
  allModels: readonly ModelWithConnectivityStatus[]
  usageDays: UsagePeriodDays
  onUsageDaysChange: (days: UsagePeriodDays) => void
  canWrite: boolean
  onTestAll?: () => void
  onTestUntested?: () => void
  onResyncAll?: () => void
  untestedTestableCount?: number
  testingAll?: boolean
  onDeleteFailed?: () => void
  deletingFailed?: boolean
  resyncingAll?: boolean
  batchBusy?: boolean
  onRefresh?: () => void
  isRefreshing?: boolean
  onRegister?: () => void
  onPreloadRegister?: () => void
  /** 通道筛选说明 Tooltip 内容；缺省用内置 hint */
  channelHint?: ReactNode
  /** 删除筛选下全部等二级操作 */
  deleteAllFilteredSlot?: ReactNode
}

export interface GatewayModelBatchBarProps {
  capabilities: GatewayModelListCapabilities
  selectedCount: number
  selectableCount: number
  allSelectableSelected: boolean
  someSelectableSelected: boolean
  onToggleSelectAll: (selected: boolean) => void
  onBatchTestSelected?: () => void
  onBatchResyncSelected?: () => void
  onBatchDelete?: () => void
  batchBusy?: boolean
  testingAll?: boolean
  resyncingAll?: boolean
}

export interface GatewayModelListShellProps {
  capabilities: GatewayModelListCapabilities
  bannerSlot?: ReactNode
  connectivityBanner?: ReactNode
  toolbar?: ReactNode
  batchBar?: ReactNode
  headerSlot?: ReactNode
  isLoading?: boolean
  isEmpty?: boolean
  emptySlot?: ReactNode
  children: ReactNode
  paginationSlot?: ReactNode
  dialogsSlot?: ReactNode
  className?: string
}

export interface GatewayModelGroupedListProps extends GatewayModelListRowPermissions {
  capabilities: GatewayModelListCapabilities
  teams: readonly GatewayTeam[]
  itemsByTeamId: ReadonlyMap<string, readonly GatewayModelListItem[]>
  tenantIdsWithModels: ReadonlySet<string>
  requiresSearch: boolean
  isLoading: boolean
  currentPage: number
  isPlatformAdmin: boolean
  /** member+ 贡献者：分组内「添加模型」入口对自有凭据开放（行级管理仍由 canManage 裁剪） */
  canContribute?: boolean
  viewerUserId?: string | null
  updatePendingModelId?: string | null
  deletingModelId?: string | null
  getModelHref: (teamId: string, modelId: string) => string
  onPreloadNavigate?: () => void
  onToggleEnabled: (item: GatewayModelListItem, teamId: string, enabled: boolean) => void
  onDelete: (item: GatewayModelListItem, teamId: string) => void
  renderTrailingActions?: (
    item: GatewayModelListItem,
    teamId: string,
    ctx: { canManage: boolean; canDelete: boolean; isUpdating: boolean; isDeleting: boolean }
  ) => ReactNode
  selectedIds?: ReadonlySet<string>
  onBatchSelectChange?: (id: string, selected: boolean) => void
  highlightModelId?: string
  usageDays?: UsagePeriodDays
  usageByRouteName?: ReadonlyMap<string, GatewayModelRouteUsageItem>
  usageLoading?: boolean
}
