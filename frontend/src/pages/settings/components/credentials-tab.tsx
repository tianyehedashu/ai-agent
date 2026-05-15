/**
 * 我的凭据 Tab：个人凭据面板 + 模型清单；导入至团队需团队写权限。
 */

import type React from 'react'

import { useMutation } from '@tanstack/react-query'
import { Download } from 'lucide-react'

import { gatewayApi } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PersonalCredentialsPanel } from '@/features/gateway-credentials/personal-credentials-panel'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'
import { useUserStore } from '@/stores/user'

import { ModelTab } from './model-tab'

export function CredentialsTab(): React.JSX.Element {
  const { toast } = useToast()
  const { currentUser } = useUserStore()
  const { canWrite } = useGatewayPermission()
  const isAnonymous = currentUser?.is_anonymous ?? true
  const showImport = canWrite && !isAnonymous

  const importMutation = useMutation({
    mutationFn: gatewayApi.importFromUserConfig,
    onSuccess: (r) => {
      toast({
        title: '导入完成',
        description: `已导入 ${String(r.created)} 条`,
      })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '导入失败', description: e.message })
    },
  })

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle>我的凭据</CardTitle>
          {showImport ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                importMutation.mutate()
              }}
              disabled={importMutation.isPending}
            >
              <Download className="mr-1.5 h-4 w-4" />
              {importMutation.isPending ? '导入中…' : '导入'}
            </Button>
          ) : null}
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="providers">
            <TabsList className="mb-4">
              <TabsTrigger value="providers">提供商</TabsTrigger>
              <TabsTrigger value="models">模型</TabsTrigger>
            </TabsList>
            <TabsContent value="providers">
              <PersonalCredentialsPanel layout="settings" />
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
