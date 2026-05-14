import { useEffect, useState } from 'react'

import { useSearchParams } from 'react-router-dom'

import { userApi, type UpdateUserParams } from '@/api/user'
import { useTheme } from '@/components/theme-provider'
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
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/hooks/use-toast'
import { useUserStore } from '@/stores/user'

import { ApiKeyTab } from './components/api-key-tab'
import { CredentialsTab } from './components/credentials-tab'
import { MCPTab } from './components/mcp-tab'

const SETTINGS_TABS = ['general', 'api', 'credentials', 'mcp', 'account'] as const
type SettingsTab = (typeof SETTINGS_TABS)[number]

export default function SettingsPage(): React.JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams()
  const { theme, setTheme } = useTheme()
  const { currentUser, setCurrentUser } = useUserStore()
  const { toast } = useToast()

  // 账户设置状态
  const [userName, setUserName] = useState('')
  const [vendorCreatorId, setVendorCreatorId] = useState<string>('')
  const [isSaving, setIsSaving] = useState(false)

  const tabParam = searchParams.get('tab')
  const activeTab: SettingsTab = SETTINGS_TABS.includes(tabParam as SettingsTab)
    ? (tabParam as SettingsTab)
    : 'general'

  const handleTabChange = (value: string): void => {
    const next = new URLSearchParams(searchParams)
    if (value === 'general') {
      next.delete('tab')
    } else {
      next.set('tab', value)
    }
    setSearchParams(next, { replace: true })
  }

  // 深链 ?tab= 与无效值时纠回允许的标签
  useEffect(() => {
    if (tabParam !== null && tabParam !== '' && !SETTINGS_TABS.includes(tabParam as SettingsTab)) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.delete('tab')
          return next
        },
        { replace: true }
      )
    }
  }, [tabParam, setSearchParams])
  useEffect(() => {
    if (currentUser) {
      setUserName(currentUser.name)
      setVendorCreatorId(
        currentUser.vendor_creator_id !== undefined && currentUser.vendor_creator_id !== null
          ? String(currentUser.vendor_creator_id)
          : ''
      )
    }
  }, [currentUser])

  // 保存账户设置
  const handleSaveAccount = async (): Promise<void> => {
    if (!currentUser || currentUser.is_anonymous) {
      toast({
        title: '无法保存',
        description: '请先登录',
        variant: 'destructive',
      })
      return
    }

    setIsSaving(true)
    try {
      const params: UpdateUserParams = {}

      // 只有当值变化时才提交
      if (userName !== currentUser.name) {
        params.name = userName
      }

      const newVendorId = vendorCreatorId ? parseInt(vendorCreatorId, 10) : null
      if (newVendorId !== currentUser.vendor_creator_id) {
        params.vendor_creator_id = newVendorId
      }

      if (Object.keys(params).length === 0) {
        toast({
          title: '无变化',
          description: '没有需要保存的更改',
        })
        return
      }

      const updatedUser = await userApi.updateUser(params)
      // 更新本地状态
      setCurrentUser({
        ...currentUser,
        name: updatedUser.name,
        vendor_creator_id: updatedUser.vendor_creator_id,
      })

      toast({
        title: '保存成功',
        description: '账户信息已更新',
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
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-bold">设置</h1>

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList className="mb-6">
          <TabsTrigger value="general">通用</TabsTrigger>
          <TabsTrigger value="api">API 密钥</TabsTrigger>
          <TabsTrigger value="credentials">我的凭据</TabsTrigger>
          <TabsTrigger value="mcp">MCP 服务器</TabsTrigger>
          <TabsTrigger value="account">账户</TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <Card>
            <CardHeader>
              <CardTitle>通用设置</CardTitle>
              <CardDescription>配置应用的基本设置</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <Label>主题</Label>
                  <p className="text-sm text-muted-foreground">选择您喜欢的主题</p>
                </div>
                <Select
                  value={theme}
                  onValueChange={(v) => {
                    setTheme(v as 'light' | 'dark' | 'system')
                  }}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light">浅色</SelectItem>
                    <SelectItem value="dark">深色</SelectItem>
                    <SelectItem value="system">跟随系统</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <Label>通知</Label>
                  <p className="text-sm text-muted-foreground">接收桌面通知</p>
                </div>
                <Switch />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <Label>声音</Label>
                  <p className="text-sm text-muted-foreground">播放通知声音</p>
                </div>
                <Switch />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="api">
          <ApiKeyTab />
        </TabsContent>

        <TabsContent value="credentials">
          <CredentialsTab />
        </TabsContent>

        <TabsContent value="mcp">
          <MCPTab />
        </TabsContent>

        <TabsContent value="account">
          <Card>
            <CardHeader>
              <CardTitle>账户设置</CardTitle>
              <CardDescription>管理您的账户信息</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label>邮箱</Label>
                <Input value={currentUser?.email ?? ''} disabled />
              </div>

              <div className="space-y-2">
                <Label>用户名</Label>
                <Input
                  value={userName}
                  onChange={(e) => {
                    setUserName(e.target.value)
                  }}
                  placeholder="请输入用户名"
                  disabled={currentUser?.is_anonymous}
                />
              </div>

              <div className="space-y-2">
                <Label>厂商用户 ID</Label>
                <Input
                  type="number"
                  value={vendorCreatorId}
                  onChange={(e) => {
                    setVendorCreatorId(e.target.value)
                  }}
                  placeholder="用于视频生成等第三方服务追踪"
                  disabled={currentUser?.is_anonymous}
                />
                <p className="text-xs text-muted-foreground">
                  此 ID 用于 GIIKIN 等视频生成服务的操作追踪，请向服务商获取您的用户 ID
                </p>
              </div>

              <Button onClick={handleSaveAccount} disabled={isSaving || currentUser?.is_anonymous}>
                {isSaving ? '保存中...' : '保存更改'}
              </Button>

              {currentUser?.is_anonymous && (
                <p className="text-sm text-muted-foreground">请先登录以修改账户设置</p>
              )}

              <div className="border-t pt-6">
                <h4 className="mb-2 text-sm font-medium text-destructive">危险区域</h4>
                <Button variant="destructive" size="sm" disabled={currentUser?.is_anonymous}>
                  删除账户
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
