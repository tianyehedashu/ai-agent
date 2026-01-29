/**
 * MCP 服务器编辑对话框
 *
 * 使用项目表单框架：react-hook-form + zod + Form/FormField；
 * 高级配置（env_config）以 JSON 编辑，与后端存储一致。
 */

import { useEffect, useState } from 'react'
import type React from 'react'

import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { mcpApi } from '@/api/mcp'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import type { MCPServerConfig } from '@/types/mcp'

const formSchema = z.object({
  display_name: z.string().max(200, '显示名称不能超过200个字符').optional(),
  url: z.string().min(1, '请输入服务器 URL').max(2000, 'URL 过长'),
  enabled: z.boolean(),
})

type FormValues = z.infer<typeof formSchema>

interface EditDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  server: MCPServerConfig | null
}

const ENV_CONFIG_EMPTY_JSON = '{}'

export function EditDialog({
  open,
  onOpenChange,
  server,
}: EditDialogProps): React.ReactElement {
  const queryClient = useQueryClient()
  const [envConfigJson, setEnvConfigJson] = useState(ENV_CONFIG_EMPTY_JSON)
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      display_name: '',
      url: '',
      enabled: true,
    },
  })

  useEffect(() => {
    if (open && server) {
      form.reset({
        display_name: server.display_name ?? server.name,
        url: server.url,
        enabled: server.enabled,
      })
      const config = server.env_config
      setEnvConfigJson(
        config && Object.keys(config).length > 0
          ? JSON.stringify(config, null, 2)
          : ENV_CONFIG_EMPTY_JSON
      )
    }
  }, [open, server, form])

  const updateMutation = useMutation({
    mutationFn: (data: FormValues & { env_config?: Record<string, unknown> }) =>
      server
        ? mcpApi.updateServer(server.id, {
            display_name: data.display_name?.trim() || undefined,
            url: data.url.trim(),
            enabled: data.enabled,
            env_config: data.env_config,
          })
        : Promise.reject(new Error('No server')),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
      queryClient.invalidateQueries({ queryKey: ['mcp-server-tools', server?.id] }).catch(() => {})
      onOpenChange(false)
      toast.success('服务器已更新')
    },
    onError: (error: Error) => {
      toast.error(`更新失败: ${error.message}`)
    },
  })

  const onSubmit = (values: FormValues): void => {
    let env_config: Record<string, unknown> | undefined
    const trimmed = envConfigJson.trim()
    if (trimmed) {
      try {
        const parsed = JSON.parse(trimmed)
        if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
          toast.error('高级配置必须是 JSON 对象')
          return
        }
        env_config = parsed as Record<string, unknown>
      } catch {
        toast.error('高级配置 JSON 格式无效，请检查后重试')
        return
      }
    } else {
      env_config = {}
    }
    updateMutation.mutate({
      ...values,
      display_name: values.display_name?.trim() || undefined,
      url: values.url.trim(),
      env_config,
    })
  }

  const visible = open && server !== null

  return (
    <Dialog open={visible} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>编辑 MCP 服务器</DialogTitle>
          <DialogDescription>
            修改显示名称、URL 或启用状态。服务器标识符「{server?.name}」不可修改。
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 py-4">
            <FormField
              control={form.control}
              name="display_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>显示名称</FormLabel>
                  <FormControl>
                    <Input placeholder={server?.name ?? 'my-mcp-server'} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>服务器 URL</FormLabel>
                  <FormControl>
                    <Input placeholder="stdio://mcp-server 或 https://..." {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="enabled"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between space-x-2 rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <FormLabel>启用</FormLabel>
                    <FormDescription>
                      禁用后，该服务器及其工具将不可用
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      disabled={updateMutation.isPending}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
              <CollapsibleTrigger asChild>
                <Button type="button" variant="ghost" size="sm" className="w-full justify-start gap-2">
                  {advancedOpen ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  高级配置（JSON）
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="space-y-2 rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">
                    环境变量、工作目录等，以 JSON 对象编辑，与后端存储一致。留空或 {'{}'} 表示无额外配置。
                  </p>
                  <textarea
                    className="min-h-[120px] w-full resize-y rounded-md border bg-muted/50 px-3 py-2 font-mono text-xs"
                    value={envConfigJson}
                    onChange={(e) => setEnvConfigJson(e.target.value)}
                    placeholder='{"env": {}, "cwd": "."}'
                    spellCheck={false}
                  />
                </div>
              </CollapsibleContent>
            </Collapsible>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  onOpenChange(false)
                }}
                disabled={updateMutation.isPending}
              >
                取消
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? '保存中...' : '保存'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
