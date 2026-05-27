/**
 * 凭据编辑场景下「当前 API Key」字段：
 *
 * - 默认显示后端返回的掩码（`sk-1…2345`），不持有完整密钥
 * - 打开「显示完整密钥」Switch 后，按需调用上层注入的 `revealFn` 拉取明文
 * - 关闭 Switch 立即清空内存中的明文，避免在 React tree 长期驻留
 * - 可编辑场景下点「更换」原地切换为 password 输入；与 reveal 互斥
 *
 * 团队/系统凭据详情页（`pages/gateway/credential-detail.tsx`）与个人凭据
 * 编辑弹窗（`features/gateway-credentials/personal-credentials-panel.tsx`）
 * 共用此组件以保持 UI 一致。
 */

import type React from 'react'
import { useId, useState } from 'react'

import { useMutation } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/hooks/use-toast'

export interface CurrentApiKeyFieldProps {
  /** Label 文案：查看模式为「当前 {label}」，更换模式为「新 {label}」 */
  label: string
  /** 后端解密后返回的掩码（如 `sk-1…2345`） */
  maskedValue: string
  /** 调用 reveal 接口拉取完整明文；只在用户主动打开开关时触发 */
  revealFn: () => Promise<{ api_key: string }>
  /** 是否允许 reveal；为 false 时仅展示掩码，不渲染开关 */
  canReveal?: boolean
  /** 是否允许轮换密钥（编辑凭据场景） */
  editable?: boolean
  /** 更换模式下的新密钥值（受控） */
  newKeyValue?: string
  onNewKeyValueChange?: (value: string) => void
  apiKeyPlaceholder?: string
  apiKeyHelpText?: string
}

export function CurrentApiKeyField({
  label,
  maskedValue,
  revealFn,
  canReveal = true,
  editable = false,
  newKeyValue = '',
  onNewKeyValueChange,
  apiKeyPlaceholder,
  apiKeyHelpText,
}: Readonly<CurrentApiKeyFieldProps>): React.JSX.Element {
  const inputId = useId()
  const switchId = useId()
  const { toast } = useToast()
  const [showFull, setShowFull] = useState(false)
  const [revealed, setRevealed] = useState<string | null>(null)
  const [rotating, setRotating] = useState(false)

  const reveal = useMutation({
    mutationFn: revealFn,
    onSuccess: (data) => {
      setRevealed(data.api_key)
    },
    onError: (e: Error) => {
      toast({
        variant: 'destructive',
        title: '无法显示完整密钥',
        description: e.message,
      })
      setShowFull(false)
    },
  })

  const clearReveal = (): void => {
    setShowFull(false)
    setRevealed(null)
    reveal.reset()
  }

  const startRotate = (): void => {
    clearReveal()
    setRotating(true)
  }

  const cancelRotate = (): void => {
    setRotating(false)
    onNewKeyValueChange?.('')
  }

  const displayValue = showFull
    ? reveal.isPending && revealed === null
      ? '加载中…'
      : (revealed ?? '')
    : maskedValue

  const showRevealControls = canReveal && !rotating
  const showRotateButton = editable && !rotating

  return (
    <div className="space-y-1.5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <Label htmlFor={inputId}>{rotating ? `新 ${label}` : `当前 ${label}`}</Label>
        <div className="flex items-center gap-2 sm:pb-0.5">
          {showRevealControls ? (
            <>
              <Label
                htmlFor={switchId}
                className="cursor-pointer text-xs font-normal text-muted-foreground"
              >
                显示完整密钥
              </Label>
              <Switch
                id={switchId}
                checked={showFull}
                disabled={reveal.isPending}
                onCheckedChange={(checked) => {
                  setShowFull(checked)
                  if (!checked) {
                    setRevealed(null)
                    reveal.reset()
                    return
                  }
                  reveal.mutate()
                }}
              />
            </>
          ) : null}
          {showRotateButton ? (
            <Button
              type="button"
              variant="link"
              size="sm"
              className="h-auto px-0"
              onClick={startRotate}
            >
              更换
            </Button>
          ) : null}
          {rotating ? (
            <Button
              type="button"
              variant="link"
              size="sm"
              className="h-auto px-0"
              onClick={cancelRotate}
            >
              取消
            </Button>
          ) : null}
        </div>
      </div>
      {rotating ? (
        <>
          <Input
            id={inputId}
            type="password"
            autoComplete="new-password"
            value={newKeyValue}
            placeholder={apiKeyPlaceholder}
            onChange={(e) => {
              onNewKeyValueChange?.(e.target.value)
            }}
          />
          {apiKeyHelpText ? (
            <p className="text-xs text-muted-foreground">{apiKeyHelpText}</p>
          ) : null}
        </>
      ) : (
        <Input id={inputId} readOnly className="font-mono text-xs" value={displayValue} />
      )}
    </div>
  )
}
