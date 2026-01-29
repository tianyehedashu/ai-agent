import { useState } from 'react'

import { Eye, EyeOff } from 'lucide-react'

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

import { MCPTab } from './components/mcp-tab'
import { ProviderConfigTab } from './components/provider-config-tab'

export default function SettingsPage(): React.JSX.Element {
  const { theme, setTheme } = useTheme()

  return (
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-bold">设置</h1>

      <Tabs defaultValue="general">
        <TabsList className="mb-6">
          <TabsTrigger value="general">通用</TabsTrigger>
          <TabsTrigger value="api">API 密钥</TabsTrigger>
          <TabsTrigger value="providers">大模型配置</TabsTrigger>
          <TabsTrigger value="mcp">MCP 工具</TabsTrigger>
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
          <Card>
            <CardHeader>
              <CardTitle>API 密钥</CardTitle>
              <CardDescription>配置 LLM 服务的 API 密钥</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <ApiKeyInput label="Anthropic API Key" name="anthropic" />
              <ApiKeyInput label="OpenAI API Key" name="openai" />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="providers">
          <ProviderConfigTab />
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
                <Input value="user@example.com" disabled />
              </div>

              <div className="space-y-2">
                <Label>用户名</Label>
                <Input defaultValue="User" />
              </div>

              <Button>保存更改</Button>

              <div className="border-t pt-6">
                <h4 className="mb-2 text-sm font-medium text-destructive">危险区域</h4>
                <Button variant="destructive" size="sm">
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

function ApiKeyInput({
  label,
  name: _name,
}: Readonly<{ label: string; name: string }>): React.JSX.Element {
  const [showKey, setShowKey] = useState(false)
  const [value, setValue] = useState('')

  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Input
            type={showKey ? 'text' : 'password'}
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
            }}
            placeholder={`输入您的 ${label}`}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2"
            onClick={() => {
              setShowKey(!showKey)
            }}
          >
            {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
        </div>
        <Button>保存</Button>
      </div>
    </div>
  )
}
