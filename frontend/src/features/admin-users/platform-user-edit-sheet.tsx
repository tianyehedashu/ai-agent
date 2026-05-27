import { useEffect, useState } from 'react'
import type React from 'react'

import { Loader2 } from 'lucide-react'

import { adminUsersApi, type PlatformRole, type PlatformUserSummary } from '@/api/adminUsers'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Switch } from '@/components/ui/switch'
import { platformRoleLabel } from '@/features/admin-users/platform-user-role-labels'
import { useToast } from '@/hooks/use-toast'

export interface PlatformUserEditSheetProps {
  user: PlatformUserSummary | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: (user: PlatformUserSummary) => void
}

export function PlatformUserEditSheet({
  user,
  open,
  onOpenChange,
  onSaved,
}: PlatformUserEditSheetProps): React.JSX.Element {
  const { toast } = useToast()
  const [name, setName] = useState('')
  const [avatarUrl, setAvatarUrl] = useState('')
  const [vendorCreatorId, setVendorCreatorId] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [role, setRole] = useState<PlatformRole>('user')
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (!user) return
    setName(user.name ?? '')
    setAvatarUrl(user.avatar_url ?? '')
    setVendorCreatorId(user.vendor_creator_id !== null ? String(user.vendor_creator_id) : '')
    setIsActive(user.is_active)
    setRole(user.role)
  }, [user])

  const handleSave = async (): Promise<void> => {
    if (!user) return

    setIsSaving(true)
    try {
      const trimmedName = name.trim()
      const trimmedAvatar = avatarUrl.trim()
      const vendorIdRaw = vendorCreatorId.trim()
      const vendorIdParsed = vendorIdRaw === '' ? null : Number.parseInt(vendorIdRaw, 10)

      if (vendorIdRaw !== '' && Number.isNaN(vendorIdParsed)) {
        toast({
          title: '厂商 ID 无效',
          description: '请输入整数或留空',
          variant: 'destructive',
        })
        return
      }

      const payload: Parameters<typeof adminUsersApi.update>[1] = {}
      if (trimmedName !== (user.name ?? '')) {
        payload.name = trimmedName || null
      }
      if (trimmedAvatar !== (user.avatar_url ?? '')) {
        payload.avatar_url = trimmedAvatar || null
      }
      if (vendorIdParsed !== user.vendor_creator_id) {
        payload.vendor_creator_id = vendorIdParsed
      }
      if (isActive !== user.is_active) {
        payload.is_active = isActive
      }

      if (Object.keys(payload).length === 0 && role === user.role) {
        onOpenChange(false)
        return
      }

      let updated = user
      if (Object.keys(payload).length > 0) {
        updated = await adminUsersApi.update(user.id, payload)
      }
      if (role !== user.role) {
        updated = await adminUsersApi.setPlatformRole(user.id, role)
      }

      onSaved(updated)
      onOpenChange(false)
      toast({
        title: '已保存用户',
        description: updated.email,
      })
    } catch (error) {
      toast({
        title: '保存失败',
        description: error instanceof Error ? error.message : '未知错误',
        variant: 'destructive',
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle>编辑用户</SheetTitle>
          <SheetDescription className="text-left">
            {user?.email ?? '选择用户以编辑资料与平台角色'}
          </SheetDescription>
        </SheetHeader>

        {user ? (
          <div className="flex-1 space-y-4 overflow-y-auto py-2">
            <div className="space-y-2">
              <Label htmlFor="platform-user-name">姓名</Label>
              <Input
                id="platform-user-name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value)
                }}
                placeholder="用户姓名"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="platform-user-avatar">头像 URL</Label>
              <Input
                id="platform-user-avatar"
                value={avatarUrl}
                onChange={(e) => {
                  setAvatarUrl(e.target.value)
                }}
                placeholder="https://..."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="platform-user-vendor-id">厂商 Creator ID</Label>
              <Input
                id="platform-user-vendor-id"
                value={vendorCreatorId}
                onChange={(e) => {
                  setVendorCreatorId(e.target.value)
                }}
                placeholder="留空表示清除"
                inputMode="numeric"
              />
            </div>

            <div className="flex items-center justify-between rounded-md border p-3">
              <div className="space-y-0.5">
                <Label htmlFor="platform-user-active">账号启用</Label>
                <p className="text-xs text-muted-foreground">禁用后用户无法登录</p>
              </div>
              <Switch id="platform-user-active" checked={isActive} onCheckedChange={setIsActive} />
            </div>

            <div className="space-y-2">
              <Label>平台角色</Label>
              <Select
                value={role}
                onValueChange={(value) => {
                  setRole(value as PlatformRole)
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">{platformRoleLabel('admin')}</SelectItem>
                  <SelectItem value="user">{platformRoleLabel('user')}</SelectItem>
                  <SelectItem value="viewer">{platformRoleLabel('viewer')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        ) : null}

        <SheetFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              onOpenChange(false)
            }}
            disabled={isSaving}
          >
            取消
          </Button>
          <Button
            type="button"
            onClick={() => {
              void handleSave()
            }}
            disabled={isSaving || !user}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                保存中…
              </>
            ) : (
              '保存'
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
