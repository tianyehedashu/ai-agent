/**
 * API Key 编辑对话框
 */

import { useEffect, useState } from 'react'
import type React from 'react'

import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm, useWatch } from 'react-hook-form'
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
import { ApiKeyGrantEditor, type GrantDraft } from '@/features/api-key-gateway/api-key-grant-editor'
import {
  gatewayGrantsToDrafts,
  grantsToRequests,
} from '@/features/api-key-gateway/api-key-grant-editor-utils'
import { applyApiFieldErrors, apiErrorFormMessage } from '@/lib/api-form-errors'
import type { ApiKey, ApiKeyScope } from '@/types/api-key'
import {
  EXPIRATION_OPTIONS,
  isReservedApiKeyScope,
  SCOPES_FOR_SELECT_ALL,
  SCOPE_DISPLAY_INFO,
} from '@/types/api-key'

const formSchema = z.object({
  name: z.string().min(1, '请输入名称').max(100, '名称不能超过100个字符'),
  description: z.string().optional(),
  scopes: z.array(z.string()).min(1, '请至少选择一个作用域'),
  extendExpiryDays: z.number().optional(),
})

type FormValues = z.infer<typeof formSchema>

interface ApiKeyEditDialogProps {
  apiKey: ApiKey | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

export function ApiKeyEditDialog({
  apiKey,
  open,
  onOpenChange,
  onSuccess,
}: ApiKeyEditDialogProps): React.ReactElement {
  const [grantDrafts, setGrantDrafts] = useState<GrantDraft[]>([])

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      scopes: [],
      extendExpiryDays: undefined,
    },
  })

  useEffect(() => {
    if (!apiKey || !open) return
    form.reset({
      name: apiKey.name,
      description: apiKey.description ?? '',
      scopes: [...apiKey.scopes],
      extendExpiryDays: undefined,
    })
    setGrantDrafts(gatewayGrantsToDrafts(apiKey.gateway_grants))
  }, [apiKey, open, form])

  const updateMutation = useMutation({
    mutationFn: (payload: Parameters<typeof apiKeyApi.update>[1]) => {
      if (!apiKey) throw new Error('missing api key')
      return apiKeyApi.update(apiKey.id, payload)
    },
    onSuccess: () => {
      toast.success('API Key 已更新')
      onSuccess?.()
      onOpenChange(false)
    },
    onError: (error: Error) => {
      if (!applyApiFieldErrors(error, form.setError)) {
        toast.error(apiErrorFormMessage(error, '更新失败'))
      } else {
        toast.error(apiErrorFormMessage(error, '请检查表单字段'))
      }
    },
  })

  const scopes = useWatch({ control: form.control, name: 'scopes' })
  const hasGatewayProxy = scopes.includes('gateway:proxy')

  const onSubmit = (values: FormValues): void => {
    if (!apiKey) return
    updateMutation.mutate({
      name: values.name,
      description: values.description ?? undefined,
      scopes: values.scopes as ApiKeyScope[],
      extend_expiry_days: values.extendExpiryDays,
      gateway_grants: hasGatewayProxy ? grantsToRequests(grantDrafts) : [],
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>编辑 API Key</DialogTitle>
          <DialogDescription>更新名称、作用域、有效期或 Gateway 团队授权</DialogDescription>
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
                    <Input {...field} />
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
                  <FormLabel>描述</FormLabel>
                  <FormControl>
                    <Textarea {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="extendExpiryDays"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>延长有效期（可选）</FormLabel>
                  <Select
                    onValueChange={(v) => {
                      field.onChange(v === 'none' ? undefined : Number(v))
                    }}
                    value={field.value ? String(field.value) : 'none'}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="不延长" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="none">不延长</SelectItem>
                      {EXPIRATION_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={String(option.value)}>
                          +{option.label}
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
                  <FormLabel>作用域</FormLabel>
                  <div className="max-h-48 space-y-2 overflow-y-auto rounded border p-2">
                    {(Object.keys(SCOPE_DISPLAY_INFO) as ApiKeyScope[]).map((scope) => (
                      <div key={scope} className="flex items-start gap-2">
                        <Checkbox
                          id={`edit-${scope}`}
                          checked={field.value.includes(scope)}
                          onCheckedChange={(checked) => {
                            const updated = checked
                              ? [...field.value, scope]
                              : field.value.filter((v) => v !== scope)
                            field.onChange(updated)
                          }}
                        />
                        <div className="flex-1">
                          <label htmlFor={`edit-${scope}`} className="cursor-pointer text-sm">
                            {SCOPE_DISPLAY_INFO[scope].label}
                            {isReservedApiKeyScope(scope) ? (
                              <Badge variant="outline" className="ml-2 text-[10px]">
                                预留
                              </Badge>
                            ) : null}
                          </label>
                          <p className="text-xs text-muted-foreground">
                            {SCOPE_DISPLAY_INFO[scope].description}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-2 pt-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => {
                        field.onChange([...SCOPES_FOR_SELECT_ALL])
                      }}
                    >
                      全选已实现
                    </Button>
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />

            {hasGatewayProxy ? (
              <ApiKeyGrantEditor grants={grantDrafts} onChange={setGrantDrafts} />
            ) : null}

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
              <Button type="submit" disabled={updateMutation.isPending || !apiKey}>
                {updateMutation.isPending ? '保存中…' : '保存'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
