import { useState } from 'react'

import { HardDrive, Loader2, Search } from 'lucide-react'
import { Link } from 'react-router-dom'

import { adminUsersApi, type PlatformRole, type PlatformUserSummary } from '@/api/adminUsers'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useToast } from '@/hooks/use-toast'

const PLATFORM_ROLE_LABELS: Record<PlatformRole, string> = {
  admin: '平台管理员',
  user: '普通用户',
  viewer: '只读账号',
}

function roleLabel(role: string): string {
  if (role in PLATFORM_ROLE_LABELS) {
    return PLATFORM_ROLE_LABELS[role as PlatformRole]
  }
  return role
}

export function PlatformAdminPanel(): React.JSX.Element {
  const { toast } = useToast()
  const [email, setEmail] = useState('')
  const [selectedRole, setSelectedRole] = useState<PlatformRole>('admin')
  const [foundUser, setFoundUser] = useState<PlatformUserSummary | null>(null)
  const [isLookingUp, setIsLookingUp] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  const handleLookup = async (): Promise<void> => {
    const trimmed = email.trim()
    if (!trimmed) {
      toast({
        title: '请输入邮箱',
        variant: 'destructive',
      })
      return
    }

    setIsLookingUp(true)
    setFoundUser(null)
    try {
      const user = await adminUsersApi.lookupByEmail(trimmed)
      setFoundUser(user)
      setSelectedRole(user.role)
    } catch (error) {
      toast({
        title: '查找失败',
        description: error instanceof Error ? error.message : '用户不存在',
        variant: 'destructive',
      })
    } finally {
      setIsLookingUp(false)
    }
  }

  const handleSaveRole = async (): Promise<void> => {
    if (!foundUser) return

    setIsSaving(true)
    try {
      const updated = await adminUsersApi.setPlatformRole(foundUser.id, selectedRole)
      setFoundUser(updated)
      toast({
        title: '已更新平台角色',
        description: `${updated.email} → ${roleLabel(updated.role)}`,
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
    <div className="space-y-6">
      <Alert>
        <AlertDescription>
          首个平台管理员可在后端执行（仅当尚无 admin 时）：
          <code className="mx-1 block rounded bg-muted px-2 py-1 text-xs">
            uv run python scripts/set_admin.py --email your@email.com
          </code>
          完成后刷新本页，即可为他人设置平台角色。
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>平台角色</CardTitle>
          <CardDescription>
            按邮箱查找已注册用户并设置平台角色（admin / user / viewer）
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-2">
              <Label htmlFor="admin-lookup-email">用户邮箱</Label>
              <Input
                id="admin-lookup-email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                }}
                placeholder="user@example.com"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    void handleLookup()
                  }
                }}
              />
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                void handleLookup()
              }}
              disabled={isLookingUp}
            >
              {isLookingUp ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Search className="mr-2 h-4 w-4" />
              )}
              查找
            </Button>
          </div>

          {foundUser && (
            <div className="space-y-4 rounded-md border p-4">
              <div className="space-y-1 text-sm">
                <p>
                  <span className="text-muted-foreground">姓名：</span>
                  {foundUser.name ?? '—'}
                </p>
                <p>
                  <span className="text-muted-foreground">邮箱：</span>
                  {foundUser.email}
                </p>
                <p>
                  <span className="text-muted-foreground">当前角色：</span>
                  {roleLabel(foundUser.role)}
                </p>
              </div>

              <div className="space-y-2">
                <Label>目标平台角色</Label>
                <Select
                  value={selectedRole}
                  onValueChange={(v) => {
                    setSelectedRole(v as PlatformRole)
                  }}
                >
                  <SelectTrigger className="w-full max-w-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">平台管理员</SelectItem>
                    <SelectItem value="user">普通用户</SelectItem>
                    <SelectItem value="viewer">只读账号</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button
                onClick={() => {
                  void handleSaveRole()
                }}
                disabled={isSaving || selectedRole === foundUser.role}
              >
                {isSaving ? '保存中...' : '保存角色'}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>运维入口</CardTitle>
          <CardDescription>其他仅平台管理员可用的配置</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" asChild>
            <Link to="/admin/storage">
              <HardDrive className="mr-2 h-4 w-4" />
              对象存储配置
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
