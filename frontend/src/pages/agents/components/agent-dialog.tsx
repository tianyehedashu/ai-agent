import { useEffect } from 'react'

import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { agentApi } from '@/api/agent'
import { Button } from '@/components/ui/button'
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
import { Slider } from '@/components/ui/slider'
import { Textarea } from '@/components/ui/textarea'
import type { Agent, AgentCreateInput } from '@/types'

const formSchema = z.object({
  name: z.string().min(1, '请输入名称').max(100, '名称不能超过100个字符'),
  description: z.string().optional(),
  systemPrompt: z.string().min(1, '请输入系统提示词'),
  model: z.string().min(1, '请选择模型'),
  temperature: z.number().min(0).max(2),
  maxTokens: z.number().min(1).max(128000),
  maxIterations: z.number().min(1).max(100),
})

type FormValues = z.infer<typeof formSchema>

const models = [
  { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
  { value: 'claude-3-opus-20240229', label: 'Claude 3 Opus' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  { value: 'gpt-4', label: 'GPT-4' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
]

interface AgentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  agent: Agent | null
}

export default function AgentDialog({
  open,
  onOpenChange,
  agent,
}: AgentDialogProps): React.JSX.Element {
  const queryClient = useQueryClient()
  const isEditing = !!agent

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      systemPrompt: '',
      model: 'claude-3-5-sonnet-20241022',
      temperature: 0.7,
      maxTokens: 4096,
      maxIterations: 20,
    },
  })

  useEffect(() => {
    if (agent) {
      form.reset({
        name: agent.name,
        description: agent.description ?? '',
        systemPrompt: agent.systemPrompt,
        model: agent.model,
        temperature: agent.temperature,
        maxTokens: agent.maxTokens,
        maxIterations: agent.maxIterations,
      })
    } else {
      form.reset({
        name: '',
        description: '',
        systemPrompt: '',
        model: 'claude-3-5-sonnet-20241022',
        temperature: 0.7,
        maxTokens: 4096,
        maxIterations: 20,
      })
    }
  }, [agent, form])

  const createMutation = useMutation({
    mutationFn: (data: AgentCreateInput) => agentApi.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['agents'] })
      onOpenChange(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: Partial<AgentCreateInput>) => {
      if (!agent) throw new Error('Agent is required')
      return agentApi.update(agent.id, data)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['agents'] })
      onOpenChange(false)
    },
  })

  const onSubmit = (values: FormValues): void => {
    if (isEditing) {
      updateMutation.mutate(values)
    } else {
      createMutation.mutate(values)
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditing ? '编辑 Agent' : '创建 Agent'}</DialogTitle>
          <DialogDescription>配置您的 AI Agent 的基本信息和参数</DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>名称</FormLabel>
                  <FormControl>
                    <Input placeholder="我的 Agent" {...field} />
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
                    <Textarea placeholder="描述这个 Agent 的用途..." {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="systemPrompt"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>系统提示词</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="你是一个专业的助手..."
                      className="min-h-[150px]"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>定义 Agent 的行为和角色</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="model"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>模型</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="选择模型" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {models.map((model) => (
                        <SelectItem key={model.value} value={model.value}>
                          {model.label}
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
              name="temperature"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Temperature: {field.value}</FormLabel>
                  <FormControl>
                    <Slider
                      min={0}
                      max={2}
                      step={0.1}
                      value={[field.value]}
                      onValueChange={([value]) => {
                        field.onChange(value)
                      }}
                    />
                  </FormControl>
                  <FormDescription>控制输出的随机性，0 最确定，2 最随机</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="maxTokens"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>最大 Tokens</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        {...field}
                        onChange={(e) => {
                          field.onChange(Number(e.target.value))
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="maxIterations"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>最大迭代次数</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        {...field}
                        onChange={(e) => {
                          field.onChange(Number(e.target.value))
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

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
              <Button type="submit" disabled={isLoading}>
                {isLoading ? '保存中...' : isEditing ? '保存' : '创建'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
