/**
 * API Key 创建对话框
 */

import { useState } from 'react'
import type React from 'react'

import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { apiKeyApi } from '@/api/api-key'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { ApiKeyScope } from '@/types/api-key'
import { API_KEY_SCOPE_GROUPS, EXPIRATION_OPTIONS, SCOPE_DISPLAY_INFO } from '@/types/api-key'

// 表单验证 schema
const formSchema = z.object({
  name: z.string().min(1, '请输入名称').max(100, '名称不能超过100个字符'),
  description: z.string().optional(),
  scopes: z.array(z.string()).min(1, '请至少选择一个作用域'),
  expiresIn: z.number().min(1).max(365),
})

type FormValues = z.infer<typeof formSchema>

interface ApiKeyCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

export function ApiKeyCreateDialog({
  open,
  onOpenChange,
  onSuccess,
}: ApiKeyCreateDialogProps): React.ReactElement {
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      scopes: [...API_KEY_SCOPE_GROUPS.read_only],
      expiresIn: 90,
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string; scopes: ApiKeyScope[]; expires_in_days: number }) =>
      apiKeyApi.create(data),
    onSuccess: (response) => {
      setCreatedKey(response.plain_key)
      setCopied(false)
      toast.success('API Key 创建成功，请立即复制保存')
      onSuccess?.()
    },
    onError: (error: Error) => {
      toast.error(`创建失败: ${error.message}`)
    },
  })

  const onSubmit = (values: FormValues): void => {
    createMutation.mutate({
      name: values.name,
      description: values.description,
      scopes: values.scopes as ApiKeyScope[],
      expires_in_days: values.expiresIn,
    })
  }

  const handleClose = (): void => {
    onOpenChange(false)
    setCreatedKey(null)
    setCopied(false)
    form.reset()
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        {!createdKey ? (
          <>
            <DialogHeader>
              <DialogTitle>创建 API Key</DialogTitle>
              <DialogDescription>创建新的 API Key 用于程序化访问</DialogDescription>
            </DialogHeader>

            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>名称</FormLabel>
                      <FormControl>
                        <Input placeholder="例如: 生产环境 Key" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>描述（可选）</FormLabel>
                      <FormControl>
                        <Textarea placeholder="描述这个 Key 的用途..." {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="expiresIn"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>有效期</FormLabel>
                      <Select
                        onValueChange={(v) => {
                          field.onChange(Number(v))
                        }}
                        value={String(field.value)}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {EXPIRATION_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={String(option.value)}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="scopes"
                  render={({ field }) => (
                    <FormItem>
                      <div className="mb-2 flex items-center justify-between">
                        <div>
                          <FormLabel>作用域</FormLabel>
                          <FormDescription>选择此 API Key 的权限范围</FormDescription>
                        </div>
                        <div className="flex gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => {
                              field.onChange(Object.keys(SCOPE_DISPLAY_INFO) as ApiKeyScope[])
                            }}
                          >
                            全选
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => {
                              field.onChange([])
                            }}
                          >
                            清空
                          </Button>
                        </div>
                      </div>

                      {/* 按类别分组显示作用域 */}
                      <div className="max-h-56 space-y-3 overflow-y-auto pr-2">
                        {(['Agent', 'Session', 'Memory', 'Workflow', 'System', 'MCP'] as const).map((category) => {
                          const categoryScopes = (Object.keys(SCOPE_DISPLAY_INFO) as ApiKeyScope[]).filter(
                            (scope) => SCOPE_DISPLAY_INFO[scope].category === category
                          )
                          if (categoryScopes.length === 0) return null

                          const allSelectedInCategory = categoryScopes.every((scope) =>
                            field.value?.includes(scope)
                          )
                          const someSelectedInCategory = categoryScopes.some((scope) =>
                            field.value?.includes(scope)
                          )

                          return (
                            <div key={category} className="space-y-2">
                              <div className="flex items-center gap-2">
                                <Checkbox
                                  id={`category-${category}`}
                                  checked={allSelectedInCategory}
                                  onCheckedChange={(checked) => {
                                    const updated = checked
                                      ? [
                                          ...field.value,
                                          ...categoryScopes.filter((s) => !field.value.includes(s)),
                                        ]
                                      : field.value.filter((v) => !categoryScopes.includes(v))
                                    field.onChange(updated)
                                  }}
                                />
                                <label
                                  htmlFor={`category-${category}`}
                                  className="text-sm font-medium cursor-pointer"
                                >
                                  {category === 'MCP' ? 'MCP 服务器' : category}
                                </label>
                                <Badge variant="outline" className="text-xs">
                                  {field.value?.filter((v) => categoryScopes.includes(v)).length}/
                                  {categoryScopes.length}
                                </Badge>
                              </div>
                              <div className="ml-6 space-y-1">
                                {categoryScopes.map((scope) => (
                                  <div
                                    key={scope}
                                    className="flex items-start gap-2 py-1 px-2 rounded hover:bg-muted/50"
                                  >
                                    <Checkbox
                                      id={scope}
                                      checked={field.value?.includes(scope)}
                                      onCheckedChange={(checked) => {
                                        const updated = checked
                                          ? [...field.value, scope]
                                          : field.value.filter((v) => v !== scope)
                                        field.onChange(updated)
                                      }}
                                    />
                                    <div className="flex-1">
                                      <label
                                        htmlFor={scope}
                                        className="text-sm cursor-pointer leading-none"
                                      >
                                        {SCOPE_DISPLAY_INFO[scope].label}
                                      </label>
                                      <p className="text-xs text-muted-foreground">
                                        {SCOPE_DISPLAY_INFO[scope].description}
                                      </p>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      onOpenChange(false)
                    }}
                  >
                    取消
                  </Button>
                  <Button type="submit" disabled={createMutation.isPending}>
                    {createMutation.isPending ? '创建中...' : '创建'}
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>API Key 创建成功</DialogTitle>
              <DialogDescription>
                完整密钥已保存，你可以在列表页随时查看。
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="rounded-lg border bg-muted p-4">
                <div className="mb-2 text-sm text-muted-foreground">完整的 API Key</div>
                <code className="block break-all rounded bg-background p-3 text-sm font-mono">
                  {createdKey}
                </code>
              </div>

              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  variant={copied ? 'default' : 'outline'}
                  onClick={() => {
                    navigator.clipboard.writeText(createdKey)
                    setCopied(true)
                    toast.success('已复制到剪贴板')
                  }}
                >
                  {copied ? (
                    <>
                      <svg className="mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      已复制
                    </>
                  ) : (
                    <>
                      <svg className="mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      复制 API Key
                    </>
                  )}
                </Button>
                <Button
                  onClick={handleClose}
                >
                  完成
                </Button>
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
