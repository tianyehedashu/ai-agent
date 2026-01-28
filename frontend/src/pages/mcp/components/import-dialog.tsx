/**
 * 导入 MCP 服务器对话框
 */

import { useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { mcpApi } from '@/api/mcp'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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

interface ImportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ImportDialog({ open, onOpenChange }: ImportDialogProps): React.ReactElement {
  const queryClient = useQueryClient()
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')

  // 获取模板列表
  const { data: templates } = useQuery({
    queryKey: ['mcp-templates'],
    queryFn: () => mcpApi.listTemplates(),
    enabled: open,
  })

  const selectedTemplate = templates?.find((t) => t.id === selectedTemplateId)

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
      onOpenChange(false)
      setName('')
      setUrl('')
      setSelectedTemplateId('')
      toast.success('服务器添加成功')
    },
    onError: (error: Error) => {
      toast.error(`添加失败: ${error.message}`)
    },
  })

  const handleTemplateChange = (templateId: string): void => {
    setSelectedTemplateId(templateId)
    const template = templates?.find((t) => t.id === templateId)
    if (template) {
      setName(template.name)
      setUrl(template.default_config.url)
    }
  }

  const handleAdd = (): void => {
    if (!name.trim()) {
      toast.error('请输入服务器名称')
      return
    }
    if (!url.trim()) {
      toast.error('请输入服务器 URL')
      return
    }
    addMutation.mutate({ name, url, template_id: selectedTemplateId || undefined })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
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
                {templates?.map((template) => (
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
            disabled={addMutation.isPending}
          >
            取消
          </Button>
          <Button onClick={handleAdd} disabled={addMutation.isPending}>
            {addMutation.isPending ? '添加中...' : '添加'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
