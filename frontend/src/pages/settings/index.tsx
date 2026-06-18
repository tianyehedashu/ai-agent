import { useEffect, useMemo, useState } from 'react'

import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { userApi, type UpdateUserParams } from '@/api/user'
import { useTheme } from '@/components/theme-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader, PageShell } from '@/components/ui/page-shell'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'
import { Key, Server, Settings2, Shield, UserCog } from '@/lib/lucide-icons'
import { CURRENT_USER_QUERY_KEY, useCurrentUser } from '@/stores/user'

import { ApiKeyTab } from './components/api-key-tab'
import { MCPTab } from './components/mcp-tab'
import { PlatformAdminPanel } from './components/platform-admin-panel'

const BASE_SETTINGS_TABS = ['general', 'api', 'account'] as const
const MCP_SETTINGS_TAB = 'mcp' as const
const PLATFORM_SETTINGS_TAB = 'platform' as const

type BaseSettingsTab = (typeof BASE_SETTINGS_TABS)[number]
type SettingsTab = BaseSettingsTab | typeof MCP_SETTINGS_TAB | typeof PLATFORM_SETTINGS_TAB

export default function SettingsPage(): React.JSX.Element {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { theme, setTheme } = useTheme()
  const currentUser = useCurrentUser()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { isPlatformAdmin } = useGatewayPermission()

  const settingsTabs = useMemo((): readonly SettingsTab[] => {
    const tabs: SettingsTab[] = [...BASE_SETTINGS_TABS]
    if (isPlatformAdmin) {
      tabs.splice(2, 0, MCP_SETTINGS_TAB)
      tabs.push(PLATFORM_SETTINGS_TAB)
    }
    return tabs
  }, [isPlatformAdmin])

  const [userName, setUserName] = useState('')
  const [vendorCreatorId, setVendorCreatorId] = useState<string>('')
  const [isSaving, setIsSaving] = useState(false)

  const tabParam = searchParams.get('tab')
  const viewParam = searchParams.get('view')

  useEffect(() => {
    if (tabParam === 'credentials') {
      navigate('/gateway/credentials?tab=personal', { replace: true })
      return
    }
    if (tabParam === 'models' || viewParam === 'gateway') {
      navigate('/gateway/models?tab=personal', { replace: true })
    }
  }, [tabParam, viewParam, navigate])

  const activeTab: SettingsTab = settingsTabs.includes(tabParam as SettingsTab)
    ? (tabParam as SettingsTab)
    : 'general'

  const handleTabChange = (value: string): void => {
    const next = new URLSearchParams(searchParams)
    if (value === 'general') {
      next.delete('tab')
    } else {
      next.set('tab', value)
    }
    next.delete('view')
    setSearchParams(next, { replace: true })
  }

  useEffect(() => {
    if (tabParam !== null && tabParam !== '' && !settingsTabs.includes(tabParam as SettingsTab)) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.delete('tab')
          next.delete('view')
          return next
        },
        { replace: true }
      )
    }
  }, [tabParam, setSearchParams, settingsTabs])

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

  const handleSaveAccount = async (): Promise<void> => {
    if (!currentUser) {
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
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, {
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
    <PageShell size="default" className="space-y-6">
      <PageHeader
        eyebrow="System"
        title="设置"
        description="集中管理账户、平台访问与本地工作台偏好。"
        icon={Settings2}
      />

      <Tabs
        value={activeTab}
        onValueChange={handleTabChange}
        className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)]"
      >
        <TabsList className="h-auto flex-col items-stretch justify-start gap-1 rounded-xl bg-card/70 p-2">
          <TabsTrigger value="general" className="w-full justify-start gap-2">
            <Settings2 className="h-4 w-4" />
            通用
          </TabsTrigger>
          <TabsTrigger value="api" className="w-full justify-start gap-2">
            <Key className="h-4 w-4" />
            API 密钥
          </TabsTrigger>
          {isPlatformAdmin && (
            <TabsTrigger value="mcp" className="w-full justify-start gap-2">
              <Server className="h-4 w-4" />
              MCP 服务器
            </TabsTrigger>
          )}
          <TabsTrigger value="account" className="w-full justify-start gap-2">
            <UserCog className="h-4 w-4" />
            账户
          </TabsTrigger>
          {isPlatformAdmin && (
            <TabsTrigger value="platform" className="w-full justify-start gap-2">
              <Shield className="h-4 w-4" />
              平台管理
            </TabsTrigger>
          )}
        </TabsList>

        <div className="min-w-0">
          <TabsContent value="general" className="mt-0">
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

          <TabsContent value="api" className="mt-0">
            <ApiKeyTab />
          </TabsContent>

          {isPlatformAdmin && (
            <TabsContent value="mcp" className="mt-0">
              <MCPTab />
            </TabsContent>
          )}

          <TabsContent value="account" className="mt-0">
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
                    disabled={!currentUser}
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
                    disabled={!currentUser}
                  />
                  <p className="text-xs text-muted-foreground">
                    此 ID 用于 GIIKIN 等视频生成服务的操作追踪，请向服务商获取您的用户 ID
                  </p>
                </div>

                <Button onClick={handleSaveAccount} disabled={isSaving || !currentUser}>
                  {isSaving ? '保存中...' : '保存更改'}
                </Button>

                <div className="border-t pt-6">
                  <h4 className="mb-2 text-sm font-medium text-destructive">危险区域</h4>
                  <Button variant="destructive" size="sm" disabled={!currentUser}>
                    删除账户
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {isPlatformAdmin && (
            <TabsContent value="platform" className="mt-0">
              <PlatformAdminPanel />
            </TabsContent>
          )}
        </div>
      </Tabs>
    </PageShell>
  )
}
