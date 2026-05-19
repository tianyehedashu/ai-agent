import type React from 'react'

import { Link } from 'react-router-dom'

import type { VirtualKey } from '@/api/gateway'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Eye, EyeOff, Loader2 } from '@/lib/lucide-icons'

export interface PlaygroundKeyFieldProps {
  apiKeyId: string
  apiKey: string
  showKey: boolean
  onApiKeyChange: (value: string) => void
  onShowKeyToggle: () => void
  virtualKeys: VirtualKey[]
  selectedKeyId: string | null
  selectedKey: VirtualKey | null
  isLoadingKeys: boolean
  isRevealing: boolean
  revealError: Error | null
  userEdited: boolean
  onSelectKey: (id: string | null) => void
  onUserEditedReset: () => void
}

export function PlaygroundKeyField({
  apiKeyId,
  apiKey,
  showKey,
  onApiKeyChange,
  onShowKeyToggle,
  virtualKeys,
  selectedKeyId,
  selectedKey,
  isLoadingKeys,
  isRevealing,
  revealError,
  userEdited,
  onSelectKey,
  onUserEditedReset,
}: Readonly<PlaygroundKeyFieldProps>): React.JSX.Element {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={apiKeyId}>
          虚拟 Key <span className="text-destructive">*</span>
        </Label>
        {virtualKeys.length > 0 ? (
          <Select
            value={selectedKeyId ?? '__none__'}
            onValueChange={(id) => {
              onUserEditedReset()
              onSelectKey(id === '__none__' ? null : id)
            }}
          >
            <SelectTrigger
              className="h-7 w-auto min-w-[10rem] max-w-[14rem] gap-1 px-2 text-xs"
              aria-label="选择虚拟 Key"
            >
              <SelectValue placeholder="选择 Key" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">
                <span className="text-muted-foreground">不选择（手动粘贴）</span>
              </SelectItem>
              <SelectGroup>
                <SelectLabel>可用 Key（{String(virtualKeys.length)}）</SelectLabel>
                {virtualKeys.map((k) => (
                  <SelectItem key={k.id} value={k.id}>
                    <span className="flex w-full items-center gap-2">
                      <span className="font-mono text-muted-foreground" translate="no">
                        {k.masked_key}
                      </span>
                      <span className="truncate text-foreground/90">{k.name}</span>
                    </span>
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        ) : null}
      </div>
      <div className="relative">
        <Input
          id={apiKeyId}
          value={apiKey}
          onChange={(e) => {
            onApiKeyChange(e.target.value)
          }}
          placeholder={isRevealing ? '正在获取明文…' : 'sk-gw-... 或从上方选择 Key'}
          type={showKey ? 'text' : 'password'}
          autoComplete="off"
          spellCheck={false}
          className="pr-10 font-mono"
          translate="no"
          aria-describedby={`${apiKeyId}-hint`}
        />
        <button
          type="button"
          onClick={onShowKeyToggle}
          className="absolute right-2 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={showKey ? '隐藏 Key' : '显示 Key'}
        >
          {showKey ? (
            <EyeOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Eye className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>
      <PlaygroundApiKeyHint
        hintId={`${apiKeyId}-hint`}
        isLoadingKeys={isLoadingKeys}
        isRevealing={isRevealing}
        selectedKey={selectedKey}
        keysCount={virtualKeys.length}
        userEdited={userEdited}
        revealError={revealError}
      />
    </div>
  )
}

function PlaygroundApiKeyHint({
  hintId,
  isLoadingKeys,
  isRevealing,
  selectedKey,
  keysCount,
  userEdited,
  revealError,
}: Readonly<{
  hintId: string
  isLoadingKeys: boolean
  isRevealing: boolean
  selectedKey: VirtualKey | null
  keysCount: number
  userEdited: boolean
  revealError: Error | null
}>): React.JSX.Element {
  if (isLoadingKeys) {
    return (
      <p id={hintId} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        正在加载虚拟 Key 列表…
      </p>
    )
  }
  if (revealError && selectedKey) {
    return (
      <p id={hintId} className="text-xs text-destructive">
        无法获取 Key 明文：{revealError.message}。可手动粘贴，或前往{' '}
        <Link to="/gateway/keys" className="underline-offset-4 hover:underline">
          虚拟 Key
        </Link>{' '}
        检查权限。
      </p>
    )
  }
  if (isRevealing && selectedKey) {
    return (
      <p id={hintId} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        正在获取「{selectedKey.name}」的明文…
      </p>
    )
  }
  if (userEdited) {
    return (
      <p id={hintId} className="text-xs text-muted-foreground">
        已使用手动输入的 Key；从上方下拉可切换为已保存的 Key。
      </p>
    )
  }
  if (selectedKey) {
    return (
      <p id={hintId} className="text-xs text-muted-foreground">
        已选择 <span className="text-foreground/80">{selectedKey.name}</span>
        <span className="font-mono" translate="no">
          {' '}
          ({selectedKey.masked_key})
        </span>
        。可在{' '}
        <Link to="/gateway/keys" className="text-primary underline-offset-4 hover:underline">
          虚拟 Key
        </Link>{' '}
        页管理。
      </p>
    )
  }
  if (keysCount === 0) {
    return (
      <p id={hintId} className="text-xs text-muted-foreground">
        暂无可用虚拟 Key。请前往{' '}
        <Link to="/gateway/keys" className="text-primary underline-offset-4 hover:underline">
          虚拟 Key
        </Link>{' '}
        创建，或手动粘贴{' '}
        <span className="font-mono" translate="no">
          sk-gw-*
        </span>
        。
      </p>
    )
  }
  return (
    <p id={hintId} className="text-xs text-muted-foreground">
      从上方选择 Key 或手动粘贴{' '}
      <span className="font-mono" translate="no">
        sk-gw-*
      </span>
      。
    </p>
  )
}
