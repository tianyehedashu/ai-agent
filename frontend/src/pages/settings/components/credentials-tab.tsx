/**
 * 我的凭据 Tab
 *
 * 由原「我的模型」（用户级模型）+「大模型配置」（用户级提供商配置）合并而来。
 * 新增「导入到 Gateway」按钮：把现有用户配置一键迁移成 Gateway 团队凭据。
 */

import { useMutation } from '@tanstack/react-query'
import { Download } from 'lucide-react'

import { gatewayApi } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/hooks/use-toast'
import { useUserStore } from '@/stores/user'

import { ModelTab } from './model-tab'
import { ProviderConfigTab } from './provider-config-tab'

export function CredentialsTab(): React.JSX.Element {
  const { toast } = useToast()
  const { currentUser } = useUserStore()
  const isAnonymous = currentUser?.is_anonymous ?? true

  const importMutation = useMutation({
    mutationFn: gatewayApi.importFromUserConfig,
    onSuccess: (r) => {
      toast({
        title: '导入完成',
        description: `已导入 ${String(r.created)} 条凭据到当前 Gateway 团队`,
      })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '导入失败', description: e.message })
    },
  })

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between space-y-0">
          <div>
            <CardTitle>我的凭据</CardTitle>
            <CardDescription>
              管理用户级 LLM Provider 凭据与可调用模型；可一键迁入 AI Gateway 团队
            </CardDescription>
          </div>
          {!isAnonymous && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                importMutation.mutate()
              }}
              disabled={importMutation.isPending}
            >
              <Download className="mr-1.5 h-4 w-4" />
              {importMutation.isPending ? '导入中...' : '导入到当前 Gateway 团队'}
            </Button>
          )}
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="providers">
            <TabsList className="mb-4">
              <TabsTrigger value="providers">提供商配置</TabsTrigger>
              <TabsTrigger value="models">模型清单</TabsTrigger>
            </TabsList>
            <TabsContent value="providers">
              <ProviderConfigTab />
            </TabsContent>
            <TabsContent value="models">
              <ModelTab />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
