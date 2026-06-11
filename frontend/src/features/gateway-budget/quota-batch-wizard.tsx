/**
 * 配额批量设置内联向导：替代侧边栏 Drawer，三步式引导。
 *
 * Step 1 — 选择对象（层级 + 主体/凭据/Key）
 * Step 2 — 设置限额（模型 + 周期 + 限额值 + 模板预设）
 * Step 3 — 预览确认（展开后的规则预览表 + 提交）
 *
 * 修复清单：
 * - P5: Step 1 底部实时显示「预计生成 N 条规则」
 * - P6: 上游/下游时间窗口改为下拉选项
 * - P9: 编辑模式直接跳到 Step 2
 * - P1: 全团队主体选中时添加提示文案
 * - P2: 预览表凭据列「—」改为「全部」
 * - P7: 桶标签改为「配额桶名称」+ 说明
 * - P10: 编辑模式提示旁加「删除此规则」按钮
 * - P17/P22: Legacy 凭据 Badge 改为「共享」+ Tooltip
 */

import { memo, useMemo, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { ArrowLeft, Check, ChevronRight, Loader2, Pencil, Trash2, X } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import { BudgetModelCombobox } from './budget-model-combobox'
import { QUOTA_TEMPLATES, applyQuotaTemplate } from './quota-batch-templates'
import { LAYER_LABELS } from './quota-rule-utils'
import {
  patchQuotaBatchFormForLayer,
  patchQuotaBatchFormForSubjectMode,
  type QuotaBatchFormValues,
} from './use-quota-center'

import type { BudgetModelOption } from './budget-model-options'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface QuotaBatchWizardProps {
  values: QuotaBatchFormValues
  onChange: (values: QuotaBatchFormValues) => void
  onSubmit: () => void
  onBack: () => void
  onDelete?: () => void
  disabled: boolean
  pending: boolean
  previewCount: number
  /** admin=全维度；member=仅本人 + 本人凭据的平台配额自助 */
  mode?: 'admin' | 'member'
  memberOptions: { id: string; label: string }[]
  keyOptions: { id: string; label: string }[]
  credentialOptions: { id: string; label: string; isLegacy?: boolean }[]
  metaLoading?: boolean
  modelOptions: BudgetModelOption[]
  modelsLoading?: boolean
  onModelPickerOpenChange?: (open: boolean) => void
  /** 编辑模式：锁定维度字段不可改，标题显示「编辑配额」 */
  editingRuleId?: string | null
}

type Step = 1 | 2 | 3

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function useFilteredOptions(
  options: { id: string; label: string }[],
  query: string
): { id: string; label: string }[] {
  return useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return options
    return options.filter((o) => o.label.toLowerCase().includes(q))
  }, [options, query])
}

/** 展开批量表单为预览规则列表（复用 buildBatchRules 逻辑的简化版） */
function expandPreviewRules(values: QuotaBatchFormValues): {
  layer: string
  subject: string
  credential: string
  model: string
  period: string
  usd: string
  tokens: string
  requests: string
}[] {
  const lu = values.limit_usd.trim() ? `$${values.limit_usd}` : ''
  const lt = values.limit_tokens.trim() ? values.limit_tokens : ''
  const lr = values.limit_requests.trim() ? values.limit_requests : ''
  const models = values.allModels ? [null] : values.modelNames.map((m) => m || null)
  const periodLabel =
    values.layer === 'platform'
      ? values.period === 'daily'
        ? '每日'
        : values.period === 'monthly'
          ? '每月'
          : '总额'
      : values.windowSeconds === '0'
        ? '套餐周期'
        : values.windowSeconds === '86400'
          ? '每日'
          : values.windowSeconds === '2592000'
            ? '每月'
            : `${values.windowSeconds}s`

  const rows: ReturnType<typeof expandPreviewRules> = []

  if (values.layer === 'platform') {
    const subjects: { label: string; target_kind: string; target_id?: string }[] = []
    if (values.subjectMode === 'tenant') {
      subjects.push({ label: '全团队', target_kind: 'tenant' })
    } else if (values.subjectMode === 'users') {
      for (const uid of values.userIds) {
        subjects.push({ label: uid.slice(0, 8), target_kind: 'user', target_id: uid })
      }
    } else {
      for (const _kid of values.keyIds) {
        subjects.push({ label: _kid.slice(0, 8), target_kind: 'key', target_id: _kid })
      }
    }
    for (const sub of subjects) {
      const credTargets =
        sub.target_kind === 'user' && values.credentialIds.length > 0
          ? values.credentialIds
          : [null]
      for (const credId of credTargets) {
        for (const model of models) {
          rows.push({
            layer: '平台',
            subject: sub.label,
            credential: credId ? credId.slice(0, 8) : '全部',
            model: model ?? '全模型',
            period: periodLabel,
            usd: lu,
            tokens: lt,
            requests: lr,
          })
        }
      }
    }
  } else if (values.layer === 'upstream') {
    const creds = values.allCredentials ? [null] : values.credentialIds
    for (const credId of creds) {
      for (const model of models) {
        rows.push({
          layer: '上游',
          subject: '—',
          credential: credId ? credId.slice(0, 8) : '全部凭据',
          model: model ?? '全模型',
          period: periodLabel,
          usd: lu,
          tokens: lt,
          requests: lr,
        })
      }
    }
  } else {
    for (const _kid of values.keyIds) {
      for (const model of models) {
        rows.push({
          layer: '下游',
          subject: '—',
          credential: '全部',
          model: model ?? '全模型',
          period: periodLabel,
          usd: lu,
          tokens: lt,
          requests: lr,
        })
      }
    }
  }
  return rows
}

/** 计算当前选择将生成的规则数（轻量版，不构建完整 body） */
function estimateRuleCount(values: QuotaBatchFormValues): number {
  const modelCount = values.allModels ? 1 : Math.max(values.modelNames.length, 1)
  if (values.layer === 'platform') {
    if (values.subjectMode === 'tenant') {
      return modelCount
    }
    if (values.subjectMode === 'users') {
      const credCount = values.credentialIds.length > 0 ? values.credentialIds.length : 1
      return values.userIds.length * credCount * modelCount
    }
    return values.keyIds.length * modelCount
  }
  if (values.layer === 'upstream') {
    const credCount = values.allCredentials ? 1 : Math.max(values.credentialIds.length, 1)
    return credCount * modelCount
  }
  return values.keyIds.length * modelCount
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

/** 步骤指示器 */
function StepIndicator({
  current,
  steps,
}: {
  current: Step
  steps: { label: string }[]
}): React.JSX.Element {
  return (
    <div className="flex items-center gap-1">
      {steps.map((step, i) => {
        const stepNum = (i + 1) as Step
        const isCompleted = current > stepNum
        const isActive = current === stepNum
        return (
          <div key={step.label} className="flex items-center gap-1">
            {i > 0 ? <ChevronRight className="h-4 w-4 text-muted-foreground/40" /> : null}
            <div
              className={cn(
                'flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors',
                isActive && 'bg-primary/10 text-primary',
                isCompleted && 'text-primary',
                !isActive && !isCompleted && 'text-muted-foreground'
              )}
            >
              <span
                className={cn(
                  'flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold',
                  isActive && 'bg-primary text-primary-foreground',
                  isCompleted && 'bg-primary/20 text-primary',
                  !isActive && !isCompleted && 'bg-muted text-muted-foreground'
                )}
              >
                {isCompleted ? <Check className="h-3 w-3" /> : stepNum}
              </span>
              {step.label}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** 可搜索、可全选的 Checkbox 列表 */
const SelectableList = memo(function SelectableList({
  items,
  selectedIds,
  onSelectionChange,
  searchPlaceholder,
  emptyHint,
  loading = false,
  disabled = false,
  showSelectAll = true,
}: {
  items: { id: string; label: string; isLegacy?: boolean }[]
  selectedIds: string[]
  onSelectionChange: (ids: string[]) => void
  searchPlaceholder: string
  emptyHint: string
  loading?: boolean
  disabled?: boolean
  showSelectAll?: boolean
}): React.JSX.Element {
  const [query, setQuery] = useState('')
  const filtered = useFilteredOptions(
    items.map((item) => ({ id: item.id, label: item.label })),
    query
  )
  const itemLegacyMap = useMemo(() => {
    const m = new Map<string, boolean>()
    for (const item of items) {
      if (item.isLegacy) m.set(item.id, true)
    }
    return m
  }, [items])
  const allVisibleSelected =
    filtered.length > 0 && filtered.every((item) => selectedIds.includes(item.id))
  const someVisibleSelected = filtered.some((item) => selectedIds.includes(item.id))

  const toggleAll = (): void => {
    if (allVisibleSelected) {
      const visibleIds = new Set(filtered.map((f) => f.id))
      onSelectionChange(selectedIds.filter((id) => !visibleIds.has(id)))
    } else {
      const merged = new Set([...selectedIds, ...filtered.map((f) => f.id)])
      onSelectionChange([...merged])
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
          }}
          placeholder={searchPlaceholder}
          className="h-8 text-xs"
          disabled={disabled}
        />
        {showSelectAll && filtered.length > 0 ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 shrink-0 text-xs"
            disabled={disabled || loading}
            onClick={toggleAll}
          >
            <Checkbox
              checked={allVisibleSelected ? true : someVisibleSelected ? 'indeterminate' : false}
              className="mr-1.5 h-3.5 w-3.5"
            />
            {allVisibleSelected ? '取消全选' : '全选'}
          </Button>
        ) : null}
      </div>
      <div className="max-h-44 space-y-1.5 overflow-y-auto rounded-md border p-2">
        {loading ? (
          <p className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            加载中…
          </p>
        ) : filtered.length === 0 ? (
          <p className="py-3 text-sm text-muted-foreground">{emptyHint}</p>
        ) : (
          filtered.map((item) => (
            <label
              key={item.id}
              className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-muted/40"
            >
              <Checkbox
                checked={selectedIds.includes(item.id)}
                disabled={disabled || loading}
                onCheckedChange={(checked) => {
                  const next = checked
                    ? [...selectedIds, item.id]
                    : selectedIds.filter((id) => id !== item.id)
                  onSelectionChange(next)
                }}
              />
              <span className="truncate">{item.label}</span>
              {itemLegacyMap.get(item.id) ? (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Badge
                        variant="outline"
                        className="ml-auto shrink-0 cursor-help text-[10px] text-blue-600"
                      >
                        共享
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-[220px] text-xs">
                      团队共享凭据（由管理员或系统创建），您可为其设置自助限额，仅约束您本人的消费。
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              ) : null}
            </label>
          ))
        )}
      </div>
    </div>
  )
})

/** 已选模型标签列表 */
function ModelTagList({
  modelNames,
  onRemove,
  disabled,
}: {
  modelNames: string[]
  onRemove: (name: string) => void
  disabled: boolean
}): React.JSX.Element | null {
  if (modelNames.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {modelNames.map((name) => (
        <Badge key={name} variant="secondary" className="gap-1 text-xs">
          {name}
          {!disabled ? (
            <button
              type="button"
              className="ml-0.5 rounded-full p-0.5 hover:bg-muted"
              onClick={() => {
                onRemove(name)
              }}
            >
              <X className="h-3 w-3" />
            </button>
          ) : null}
        </Badge>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Step 1: 选择对象                                                    */
/* ------------------------------------------------------------------ */

function StepTarget({
  values,
  onChange,
  disabled,
  mode,
  memberOptions,
  keyOptions,
  credentialOptions,
  metaLoading,
  editingRuleId,
}: QuotaBatchWizardProps): React.JSX.Element {
  const isEditing = !!editingRuleId
  const isMember = mode === 'member'
  const estimatedCount = useMemo(() => estimateRuleCount(values), [values])

  return (
    <div className="space-y-5">
      {isMember ? (
        /* ---- 成员模式：简化为仅选凭据 ---- */
        <div className="space-y-3">
          <div>
            <h3 className="text-sm font-medium">选择凭据</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              选择您在团队中可用的凭据，为其设置消费限额（自我约束）。
            </p>
          </div>
          <SelectableList
            items={credentialOptions}
            selectedIds={values.credentialIds}
            onSelectionChange={(ids) => {
              onChange({ ...values, credentialIds: ids })
            }}
            searchPlaceholder="搜索凭据…"
            emptyHint="暂无可用的团队凭据。如需设置配额，请先在凭据页添加团队凭据，或联系管理员。"
            loading={metaLoading}
            disabled={disabled}
          />
        </div>
      ) : (
        /* ---- 管理员模式：层级 + 主体 + 列表 ---- */
        <>
          <div className="space-y-2">
            <Label htmlFor="qbw-layer">层级</Label>
            <Select
              value={values.layer}
              onValueChange={(layer) => {
                onChange(
                  patchQuotaBatchFormForLayer(values, layer as QuotaBatchFormValues['layer'])
                )
              }}
              disabled={disabled || isEditing}
            >
              <SelectTrigger id="qbw-layer">
                <SelectValue placeholder="选择层级" />
              </SelectTrigger>
              <SelectContent>
                {(['platform', 'upstream', 'downstream'] as const).map((layer) => (
                  <SelectItem key={layer} value={layer}>
                    {LAYER_LABELS[layer]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {values.layer === 'platform'
                ? '限制本团队在 Gateway 上的消费（租户/成员/Key）。'
                : values.layer === 'upstream'
                  ? '限制上游凭据调用额度。'
                  : '为虚拟 Key 配置下游客户权益套餐桶。'}
            </p>
            {isEditing ? (
              <p className="text-xs text-amber-600">
                编辑模式下层级不可变更，如需更换请删除后新建。
              </p>
            ) : null}
          </div>

          {/* Platform 层 */}
          {values.layer === 'platform' ? (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="qbw-subject">主体</Label>
                <Select
                  value={values.subjectMode}
                  onValueChange={(mode) => {
                    onChange(
                      patchQuotaBatchFormForSubjectMode(
                        values,
                        mode as QuotaBatchFormValues['subjectMode']
                      )
                    )
                  }}
                  disabled={disabled || isEditing}
                >
                  <SelectTrigger id="qbw-subject">
                    <SelectValue placeholder="选择主体" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="tenant">全团队</SelectItem>
                    <SelectItem value="users">指定成员</SelectItem>
                    <SelectItem value="keys">虚拟 Key</SelectItem>
                  </SelectContent>
                </Select>
                {values.subjectMode === 'tenant' ? (
                  <p className="text-xs text-muted-foreground">
                    对当前团队全体生效一条平台护栏（与成员/Key
                    规则可并存）。全团队护栏不区分凭据，如需按凭据限制请选择「指定成员」。
                  </p>
                ) : null}
                {isEditing ? (
                  <p className="text-xs text-amber-600">编辑模式下主体不可变更。</p>
                ) : null}
              </div>

              {values.subjectMode === 'users' ? (
                <div className="space-y-3">
                  <div>
                    <Label>成员</Label>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      选择需要设置配额的团队成员。
                    </p>
                  </div>
                  <SelectableList
                    items={memberOptions}
                    selectedIds={values.userIds}
                    onSelectionChange={(ids) => {
                      onChange({ ...values, userIds: ids })
                    }}
                    searchPlaceholder="搜索成员…"
                    emptyHint="暂无成员，请先在团队页添加成员。"
                    loading={metaLoading}
                    disabled={disabled}
                  />

                  <div>
                    <Label>凭据（可选）</Label>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      不选 = 成员在全团队的总用量护栏；选凭据 =
                      仅限制该成员在指定凭据上的用量（成员×凭据×模型组合）。
                    </p>
                  </div>
                  <SelectableList
                    items={credentialOptions}
                    selectedIds={values.credentialIds}
                    onSelectionChange={(ids) => {
                      onChange({ ...values, credentialIds: ids })
                    }}
                    searchPlaceholder="搜索凭据…"
                    emptyHint="暂无团队凭据。"
                    loading={metaLoading}
                    disabled={disabled}
                  />
                </div>
              ) : null}

              {values.subjectMode === 'keys' ? (
                <div className="space-y-3">
                  <div>
                    <Label>虚拟 Key</Label>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      选择需要设置配额的虚拟 Key。
                    </p>
                  </div>
                  <SelectableList
                    items={keyOptions}
                    selectedIds={values.keyIds}
                    onSelectionChange={(ids) => {
                      onChange({ ...values, keyIds: ids })
                    }}
                    searchPlaceholder="搜索 Key…"
                    emptyHint="暂无虚拟 Key，请先在 Key 页创建。"
                    loading={metaLoading}
                    disabled={disabled}
                  />
                </div>
              ) : null}
            </div>
          ) : null}

          {/* Upstream 层 */}
          {values.layer === 'upstream' ? (
            <div className="space-y-3">
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <Checkbox
                  checked={values.allCredentials}
                  disabled={disabled}
                  onCheckedChange={(checked) => {
                    onChange({ ...values, allCredentials: checked === true })
                  }}
                />
                全部凭据
              </label>
              {!values.allCredentials ? (
                <div>
                  <Label>凭据</Label>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    选择需要设置上游额度的凭据。
                  </p>
                </div>
              ) : null}
              {!values.allCredentials ? (
                <SelectableList
                  items={credentialOptions}
                  selectedIds={values.credentialIds}
                  onSelectionChange={(ids) => {
                    onChange({ ...values, credentialIds: ids })
                  }}
                  searchPlaceholder="搜索凭据…"
                  emptyHint="暂无凭据，请先在凭据页添加。"
                  loading={metaLoading}
                  disabled={disabled}
                />
              ) : null}
            </div>
          ) : null}

          {/* Downstream 层 */}
          {values.layer === 'downstream' ? (
            <div className="space-y-3">
              <div>
                <Label>虚拟 Key</Label>
                <p className="mt-0.5 text-xs text-muted-foreground">选择需要设置权益的虚拟 Key。</p>
              </div>
              <SelectableList
                items={keyOptions}
                selectedIds={values.keyIds}
                onSelectionChange={(ids) => {
                  onChange({ ...values, keyIds: ids })
                }}
                searchPlaceholder="搜索 Key…"
                emptyHint="暂无虚拟 Key，请先在 Key 页创建。"
                loading={metaLoading}
                disabled={disabled}
              />
            </div>
          ) : null}
        </>
      )}

      {/* P5: 预计生成规则数提示 */}
      {estimatedCount > 0 ? (
        <div
          className={cn(
            'rounded-md border px-3 py-2 text-xs',
            estimatedCount > 100
              ? 'border-amber-300 bg-amber-50 text-amber-700'
              : 'border-muted bg-muted/30 text-muted-foreground'
          )}
        >
          {estimatedCount > 100 ? (
            <span className="font-medium">
              预计生成 {estimatedCount} 条规则 — 数量较多，请确认选择范围是否合理。单次上限 200 条。
            </span>
          ) : (
            <span>预计生成 {estimatedCount} 条规则</span>
          )}
        </div>
      ) : null}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Step 2: 设置限额                                                    */
/* ------------------------------------------------------------------ */

/** 时间窗口预设选项 */
const WINDOW_PRESETS = [
  { value: '0', label: '套餐周期' },
  { value: '86400', label: '每日（86400s）' },
  { value: '2592000', label: '每月（2592000s）' },
  { value: 'custom', label: '自定义秒数' },
] as const

function StepLimits({
  values,
  onChange,
  disabled,
  mode,
  modelOptions,
  modelsLoading,
  onModelPickerOpenChange,
  editingRuleId,
}: QuotaBatchWizardProps): React.JSX.Element {
  const isEditing = !!editingRuleId
  const isMember = mode === 'member'
  const isNonPlatform = values.layer !== 'platform' && !isMember

  // 判断当前时间窗口值是否匹配预设
  const windowPresetValue = useMemo(() => {
    if (!isNonPlatform) return '0'
    const v = values.windowSeconds.trim()
    if (v === '0') return '0'
    if (v === '86400') return '86400'
    if (v === '2592000') return '2592000'
    return 'custom'
  }, [isNonPlatform, values.windowSeconds])

  const handleWindowPresetChange = (preset: string): void => {
    if (preset === 'custom') {
      // 保留当前自定义值或清空让用户填写
      onChange({ ...values, windowSeconds: values.windowSeconds || '' })
    } else {
      onChange({ ...values, windowSeconds: preset })
    }
  }

  return (
    <div className="space-y-5">
      {/* 模型选择 */}
      <div className="space-y-2">
        <Label>模型范围</Label>
        <div className="flex items-center gap-3">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <Checkbox
              checked={values.allModels}
              disabled={disabled}
              onCheckedChange={(checked) => {
                onChange({ ...values, allModels: checked === true, modelNames: [] })
              }}
            />
            全模型
          </label>
        </div>
        {!values.allModels ? (
          <div className="space-y-2">
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <BudgetModelCombobox
                  value=""
                  onChange={(name) => {
                    if (name && !values.modelNames.includes(name)) {
                      onChange({ ...values, modelNames: [...values.modelNames, name] })
                    }
                  }}
                  options={modelOptions}
                  disabled={disabled}
                  loading={modelsLoading}
                  placeholder="添加模型…"
                  onPopoverOpenChange={onModelPickerOpenChange}
                />
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 text-xs"
                disabled={disabled || values.modelNames.length === 0}
                onClick={() => {
                  onChange({ ...values, modelNames: [] })
                }}
              >
                清空
              </Button>
            </div>
            <ModelTagList
              modelNames={values.modelNames}
              onRemove={(name) => {
                onChange({ ...values, modelNames: values.modelNames.filter((n) => n !== name) })
              }}
              disabled={disabled}
            />
            {values.modelNames.length === 0 ? (
              <p className="text-xs text-amber-600">请至少选择一个模型，或勾选"全模型"。</p>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* 周期 — Platform / 成员 */}
      {values.layer === 'platform' || isMember ? (
        <div className="space-y-2">
          <Label htmlFor="qbw-period">周期</Label>
          <Select
            value={values.period}
            onValueChange={(period) => {
              onChange({ ...values, period: period as QuotaBatchFormValues['period'] })
            }}
            disabled={disabled}
          >
            <SelectTrigger id="qbw-period">
              <SelectValue placeholder="选择周期" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="daily">每日</SelectItem>
              <SelectItem value="monthly">每月</SelectItem>
              <SelectItem value="total">总额</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ) : (
        /* P6: 上游/下游时间窗口改为下拉选项 */
        <div className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="qbw-window-preset">时间窗口</Label>
            <Select
              value={windowPresetValue}
              onValueChange={handleWindowPresetChange}
              disabled={disabled}
            >
              <SelectTrigger id="qbw-window-preset">
                <SelectValue placeholder="选择时间窗口" />
              </SelectTrigger>
              <SelectContent>
                {WINDOW_PRESETS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              套餐周期 = 跟随上游/下游套餐定义的计费周期；每日 = 86400 秒；每月 = 2592000 秒。
            </p>
          </div>
          {windowPresetValue === 'custom' ? (
            <div className="space-y-1">
              <Label htmlFor="qbw-window-custom" className="text-xs text-muted-foreground">
                自定义秒数
              </Label>
              <Input
                id="qbw-window-custom"
                type="number"
                min="1"
                value={values.windowSeconds}
                onChange={(e) => {
                  onChange({ ...values, windowSeconds: e.target.value })
                }}
                placeholder="如 3600 = 1小时"
                disabled={disabled}
                className="h-9"
              />
            </div>
          ) : null}

          {/* P7: 桶标签改为「配额桶名称」+ 说明 */}
          <div className="space-y-1">
            <Label htmlFor="qbw-label" className="text-xs text-muted-foreground">
              配额桶名称
            </Label>
            <Input
              id="qbw-label"
              value={values.quotaLabel}
              onChange={(e) => {
                onChange({ ...values, quotaLabel: e.target.value })
              }}
              placeholder="default"
              disabled={disabled}
              className="h-9"
            />
            <p className="text-xs text-muted-foreground">
              同一凭据/Key 下不同桶独立计数，默认为 default。一般无需修改。
            </p>
          </div>
        </div>
      )}

      {/* 模板预设 */}
      <div className="space-y-2">
        <Label>快捷预设</Label>
        <div className="flex flex-wrap gap-2">
          {QUOTA_TEMPLATES.map((t) => (
            <Button
              key={t.label}
              type="button"
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              disabled={disabled}
              onClick={() => {
                onChange(applyQuotaTemplate(values, t))
              }}
            >
              {t.label}
              <span className="ml-1 text-muted-foreground">{t.description}</span>
            </Button>
          ))}
        </div>
      </div>

      {/* 限额输入 */}
      <div className="space-y-3">
        <Label>限额值（至少填写一项）</Label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="space-y-1">
            <Label htmlFor="qbw-usd" className="text-xs text-muted-foreground">
              USD 限额
            </Label>
            <Input
              id="qbw-usd"
              type="number"
              step="0.01"
              min="0"
              value={values.limit_usd}
              onChange={(e) => {
                onChange({ ...values, limit_usd: e.target.value })
              }}
              placeholder="如 100"
              disabled={disabled}
              className="h-9"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="qbw-tokens" className="text-xs text-muted-foreground">
              Token 限额
            </Label>
            <Input
              id="qbw-tokens"
              type="number"
              step="1"
              min="0"
              value={values.limit_tokens}
              onChange={(e) => {
                onChange({ ...values, limit_tokens: e.target.value })
              }}
              placeholder="如 1000000"
              disabled={disabled}
              className="h-9"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="qbw-requests" className="text-xs text-muted-foreground">
              请求数限额
            </Label>
            <Input
              id="qbw-requests"
              type="number"
              step="1"
              min="0"
              value={values.limit_requests}
              onChange={(e) => {
                onChange({ ...values, limit_requests: e.target.value })
              }}
              placeholder="如 1000"
              disabled={disabled}
              className="h-9"
            />
          </div>
        </div>
      </div>

      {/* P10: 编辑模式提示 + 删除按钮 */}
      {isEditing ? (
        <div className="flex items-center justify-between rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
          <p className="text-xs text-amber-700">
            编辑模式下仅可修改限额值和模型范围，层级与主体不可变更。如需更换维度请删除后新建。
          </p>
        </div>
      ) : null}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Step 3: 预览确认                                                    */
/* ------------------------------------------------------------------ */

function StepPreview({
  values,
  previewCount,
  pending,
  mode,
}: QuotaBatchWizardProps & { previewCount: number }): React.JSX.Element {
  const isMember = mode === 'member'
  const rows = useMemo(() => expandPreviewRules(values), [values])

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium">预览即将写入的规则</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          以下 {previewCount} 条配额规则将被创建或更新。请确认无误后提交。
        </p>
      </div>

      {rows.length === 0 ? (
        <p className="py-4 text-sm text-amber-600">
          未生成任何规则，请返回上一步检查选择和限额值。
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-xs">
            <thead className="border-b bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-1.5 text-left font-medium">层级</th>
                <th className="px-3 py-1.5 text-left font-medium">主体</th>
                <th className="px-3 py-1.5 text-left font-medium">凭据</th>
                <th className="px-3 py-1.5 text-left font-medium">模型</th>
                <th className="px-3 py-1.5 text-left font-medium">周期</th>
                <th className="px-3 py-1.5 text-left font-medium">USD</th>
                <th className="px-3 py-1.5 text-left font-medium">Token</th>
                <th className="px-3 py-1.5 text-left font-medium">请求</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 50).map((row, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="px-3 py-1.5">{row.layer}</td>
                  <td className="px-3 py-1.5">{row.subject}</td>
                  <td
                    className={cn(
                      'px-3 py-1.5',
                      row.credential === '全部' && 'text-muted-foreground'
                    )}
                  >
                    {row.credential}
                  </td>
                  <td className="max-w-[120px] truncate px-3 py-1.5">{row.model}</td>
                  <td className="px-3 py-1.5">{row.period}</td>
                  <td className="px-3 py-1.5 tabular-nums">{row.usd || '—'}</td>
                  <td className="px-3 py-1.5 tabular-nums">{row.tokens || '—'}</td>
                  <td className="px-3 py-1.5 tabular-nums">{row.requests || '—'}</td>
                </tr>
              ))}
              {rows.length > 50 ? (
                <tr>
                  <td colSpan={8} className="px-3 py-2 text-center text-muted-foreground">
                    …还有 {rows.length - 50} 条未展示
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}

      {/* P15: 大批量汇总行 */}
      {rows.length > 10 ? (
        <p className="text-xs text-muted-foreground">
          共 {rows.length} 条规则，全部为相同限额配置。
        </p>
      ) : null}

      {isMember ? (
        <p className="text-xs text-muted-foreground">
          自助配额仅约束您本人在所选凭据上的消费，不影响其他成员。
        </p>
      ) : null}

      {pending ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          正在提交…
        </p>
      ) : null}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Wizard                                                        */
/* ------------------------------------------------------------------ */

export function QuotaBatchWizard(props: QuotaBatchWizardProps): React.JSX.Element {
  const {
    values,
    onSubmit,
    onBack,
    onDelete,
    disabled,
    pending,
    previewCount,
    mode = 'admin',
    editingRuleId,
  } = props

  const isMember = mode === 'member'
  const isEditing = !!editingRuleId
  // P9: 编辑模式直接跳到 Step 2
  const [step, setStep] = useState<Step>(isEditing ? 2 : 1)

  const STEPS = useMemo(
    () => [
      { label: isMember ? '选择凭据' : '选择对象' },
      { label: '设置限额' },
      { label: '预览确认' },
    ],
    [isMember]
  )

  const canGoNext = (): boolean => {
    if (step === 1) {
      if (isMember) {
        return values.credentialIds.length > 0
      }
      if (values.layer === 'platform') {
        if (values.subjectMode === 'users' && values.userIds.length === 0) return false
        if (values.subjectMode === 'keys' && values.keyIds.length === 0) return false
      }
      if (
        values.layer === 'upstream' &&
        !values.allCredentials &&
        values.credentialIds.length === 0
      )
        return false
      if (values.layer === 'downstream' && values.keyIds.length === 0) return false
      return true
    }
    if (step === 2) {
      const hasLimit =
        values.limit_usd.trim() !== '' ||
        values.limit_tokens.trim() !== '' ||
        values.limit_requests.trim() !== ''
      if (!values.allModels && values.modelNames.length === 0) return false
      return hasLimit
    }
    return true
  }

  const handleNext = (): void => {
    if (step < 3) setStep((step + 1) as Step)
  }
  const handlePrev = (): void => {
    if (step > 1) setStep((step - 1) as Step)
  }
  const handleSubmit = (): void => {
    onSubmit()
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 gap-1 px-2"
            onClick={onBack}
          >
            <ArrowLeft className="h-4 w-4" />
            返回列表
          </Button>
          <div className="flex items-center gap-2">
            {isEditing ? <Pencil className="h-4 w-4 text-muted-foreground" /> : null}
            <h2 className="text-lg font-semibold">
              {isEditing ? '编辑配额' : isMember ? '设置我的配额' : '批量设置配额'}
            </h2>
          </div>
          {/* P10: 编辑模式删除按钮 */}
          {isEditing && onDelete ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 gap-1 text-xs text-destructive hover:bg-destructive/10"
              disabled={disabled}
              onClick={onDelete}
            >
              <Trash2 className="h-3.5 w-3.5" />
              删除此规则
            </Button>
          ) : null}
        </div>
        <StepIndicator current={step} steps={STEPS} />
      </div>

      {/* Step content */}
      <div className="rounded-lg border bg-card p-5">
        {step === 1 ? <StepTarget {...props} /> : null}
        {step === 2 ? <StepLimits {...props} /> : null}
        {step === 3 ? <StepPreview {...props} previewCount={previewCount} /> : null}
      </div>

      {/* Footer navigation */}
      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground">
          {step === 3 ? (
            <span>
              将写入 <strong className="text-foreground">{previewCount}</strong> 条配额规则
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {step > 1 ? (
            <Button type="button" variant="outline" onClick={handlePrev} disabled={pending}>
              上一步
            </Button>
          ) : null}
          {step < 3 ? (
            <Button type="button" onClick={handleNext} disabled={disabled || !canGoNext()}>
              下一步
            </Button>
          ) : null}
          {step === 3 ? (
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={disabled || pending || previewCount === 0}
            >
              {pending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  提交中…
                </>
              ) : (
                `确认提交（${String(previewCount)} 条）`
              )}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
