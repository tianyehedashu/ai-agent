/**
 * MCP 工具管理标签页
 */

import { useState } from 'react'
import type React from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Power, Server } from 'lucide-react'
import { toast } from 'sonner'

import { mcpApi } from '@/api/mcp'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import { Switch } from '@/components/ui/switch'
import type { MCPTemplate } from '@/types/mcp'

export function MCPTab(): React.ReactElement {
  const queryClient = useQueryClient()
  const [addDialogOpen, setAddDialogOpen] = useState(false)

  // 获取服务器列表
  const { data: serversData, isLoading } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => mcpApi.listServers(),
  })

  // 获取模板列表
  const { data: templates } = useQuery({
    queryKey: ['mcp-templates'],
    queryFn: () => mcpApi.listTemplates(),
  })

  // 切换服务器状态
  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      mcpApi.toggleServer(id, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
      toast.success('服务器状态已更新')
    },
    onError: (error: Error) => {
      toast.error(`更新失败: ${error.message}`)
    },
  })

  // 删除服务器
  const deleteMutation = useMutation({
    mutationFn: (id: string) => mcpApi.deleteServer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
      toast.success('服务器已删除')
    },
    onError: (error: Error) => {
      toast.error(`删除失败: ${error.message}`)
    },
  })

  // 添加服务器
  const addMutation = useMutation({
    mutationFn: (data: { name: string; url: string; template_id?: string }) =>
      mcpApi.addServer({
        ...data,
        env_type: 'dynamic_injected',
        env_config: {},
        enabled: true,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
      setAddDialogOpen(false)
      toast.success('服务器添加成功')
    },
    onError: (error: Error) => {
      toast.error(`添加失败: ${error.message}`)
    },
  })

  const allServers = [...(serversData?.system_servers ?? []), ...(serversData?.user_servers ?? [])]

  if (isLoading) {
    return <div className="p-6">加载中...</div>
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">MCP 工具管理</h2>
          <p className="text-muted-foreground">管理 Model Context Protocol 服务器</p>
        </div>
        <AddServerDialog
          open={addDialogOpen}
          onOpenChange={setAddDialogOpen}
          templates={templates ?? []}
          onAdd={(data) => {
            addMutation.mutate(data)
          }}
          isLoading={addMutation.isPending}
        />
      </div>

      <div className="grid gap-4">
        {allServers.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Server className="mb-4 h-12 w-12 text-muted-foreground" />
              <p className="text-muted-foreground">暂无 MCP 服务器</p>
              <p className="mt-2 text-sm text-muted-foreground">
                点击上方按钮添加您的第一个 MCP 服务器
              </p>
            </CardContent>
          </Card>
        ) : (
          allServers.map((server) => (
            <Card key={server.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-lg">
                        {server.display_name ?? server.name}
                      </CardTitle>
                      <Badge variant={server.scope === 'system' ? 'default' : 'secondary'}>
                        {server.scope === 'system' ? '系统' : '用户'}
                      </Badge>
                      {!server.enabled && (
                        <Badge variant="outline" className="text-muted-foreground">
                          已禁用
                        </Badge>
                      )}
                    </div>
                    <CardDescription className="font-mono text-xs">{server.url}</CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={server.enabled}
                      onCheckedChange={(checked) => {
                        toggleMutation.mutate({ id: server.id, enabled: checked })
                      }}
                      disabled={toggleMutation.isPending}
                    />
                    {server.scope === 'user' && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          if (confirm('确定要删除这个服务器吗？')) {
                            deleteMutation.mutate(server.id)
                          }
                        }}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <span className="font-medium">类型:</span>
                      <span>{server.env_type}</span>
                    </div>
                    {server.enabled ? (
                      <div className="flex items-center gap-2 text-green-600">
                        <Power className="h-4 w-4" />
                        <span>运行中</span>
                      </div>
                    ) : null}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}

// 添加服务器对话框
function AddServerDialog({
  open,
  onOpenChange,
  templates,
  onAdd,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  templates: MCPTemplate[]
  onAdd: (data: { name: string; url: string; template_id?: string }) => void
  isLoading: boolean
}): React.ReactElement {
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')

  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId)

  // 当选择模板时，自动填充表单
  const handleTemplateChange = (templateId: string): void => {
    setSelectedTemplateId(templateId)
    const template = templates.find((t) => t.id === templateId)
    if (template) {
      setName(template.name)
      setUrl(template.default_config.url)
    }
  }

  const handleAdd = (): void => {
    if (!name || !url) {
      toast.error('请填写完整信息')
      return
    }
    onAdd({ name, url, template_id: selectedTemplateId || undefined })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          添加服务器
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>添加 MCP 服务器</DialogTitle>
          <DialogDescription>从模板添加或手动配置 MCP 服务器</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="template">选择模板（可选）</Label>
            <Select value={selectedTemplateId} onValueChange={handleTemplateChange}>
              <SelectTrigger id="template">
                <SelectValue placeholder="选择模板或手动输入" />
              </SelectTrigger>
              <SelectContent>
                {templates.map((template) => (
                  <SelectItem key={template.id} value={template.id}>
                    <div className="flex items-center gap-2">
                      <span>{template.display_name}</span>
                      <Badge variant="outline" className="text-xs">
                        {template.category}
                      </Badge>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedTemplate && (
              <p className="text-sm text-muted-foreground">{selectedTemplate.description}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="name">服务器名称</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => {
                setName(e.target.value)
              }}
              placeholder="my-mcp-server"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="url">服务器 URL</Label>
            <Input
              id="url"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
              }}
              placeholder="stdio://mcp-server 或 https://..."
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button onClick={handleAdd} disabled={isLoading}>
            {isLoading ? '添加中...' : '添加'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
