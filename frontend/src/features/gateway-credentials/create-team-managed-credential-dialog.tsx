/**
 * 团队/系统凭据创建弹窗（POST /gateway/credentials）
 */

import { useEffect, useState } from 'react'
import type React from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import { TEAM_MANAGED_CREDENTIAL_PROVIDER_IDS, credentialProviderLabel } from './constants'

export interface TeamManagedCredentialCreateValues {
  provider: string
  name: string
  api_key: string
  api_base?: string
  scope: 'team' | 'system'
}

export function CreateTeamManagedCredentialDialog({
  open,
  onOpenChange,
  isPlatformAdmin,
  onSubmit,
}: Readonly<{
  open: boolean
  onOpenChange: (v: boolean) => void
  isPlatformAdmin: boolean
  onSubmit: (v: TeamManagedCredentialCreateValues) => void
}>): React.JSX.Element {
  const [values, setValues] = useState<TeamManagedCredentialCreateValues>({
    provider: 'openai',
    name: '',
    api_key: '',
    api_base: '',
    scope: 'team',
  })

  useEffect(() => {
    if (open) {
      setValues({
        provider: 'openai',
        name: '',
        api_key: '',
        api_base: '',
        scope: 'team',
      })
    }
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增凭据</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {isPlatformAdmin ? (
            <div>
              <Label>作用域</Label>
              <Select
                value={values.scope}
                onValueChange={(v) => {
                  setValues({ ...values, scope: v as 'team' | 'system' })
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="team">团队</SelectItem>
                  <SelectItem value="system">系统</SelectItem>
                </SelectContent>
              </Select>
            </div>
          ) : null}
          <div>
            <Label>名称</Label>
            <Input
              value={values.name}
              onChange={(e) => {
                setValues({ ...values, name: e.target.value })
              }}
              placeholder="主账号 / 测试线"
            />
          </div>
          <div>
            <Label>提供商</Label>
            <Select
              value={values.provider}
              onValueChange={(v) => {
                setValues({ ...values, provider: v })
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TEAM_MANAGED_CREDENTIAL_PROVIDER_IDS.map((p) => (
                  <SelectItem key={p} value={p}>
                    {credentialProviderLabel(p)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>API Key</Label>
            <Input
              type="password"
              value={values.api_key}
              onChange={(e) => {
                setValues({ ...values, api_key: e.target.value })
              }}
            />
          </div>
          <div>
            <Label>api_base（可选）</Label>
            <Input
              value={values.api_base ?? ''}
              onChange={(e) => {
                setValues({ ...values, api_base: e.target.value })
              }}
              placeholder="https://api.openai.com/v1"
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button
            onClick={() => {
              if (!values.name || !values.api_key) return
              const payload: TeamManagedCredentialCreateValues = { ...values }
              if (!isPlatformAdmin) {
                payload.scope = 'team'
              }
              onSubmit(payload)
            }}
            disabled={!values.name || !values.api_key}
          >
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
