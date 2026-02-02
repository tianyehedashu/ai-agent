/**
 * 系统 MCP（客户端直连）查看与配置页
 *
 * 展示由平台暴露的 Streamable HTTP MCP 服务器（如 llm-server / ai-agent-llm），
 * 提供 Cursor mcp.json 配置的复制，以及动态工具管理（仅管理员）。
 */

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  Copy,
  Pencil,
  Plus,
  Server,
  Settings2,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'

import { mcpApi } from '@/api/mcp'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useUserStore } from '@/stores/user'
import type {
  ClientDirectMCPServer,
  ClientMCPConfigResponse,
  CursorMCPServerConfig,
  DynamicPromptItem,
  DynamicToolAddRequest,
  DynamicToolItem,
} from '@/types/mcp'

/** 后端 scope 与 Cursor mcp.json 中常用 key 的对应（与后端 _SCOPE_TO_CURSOR_NAME 一致） */
const SCOPE_TO_CURSOR_NAME: Record<string, string> = {
  'llm-server': 'ai-agent-llm',
}

function scopeToCursorName(scope: string): string {
  return SCOPE_TO_CURSOR_NAME[scope] ?? scope.replace(/-/g, '_')
}

function copyToClipboard(text: string): void {
  navigator.clipboard
    .writeText(text)
    .then(() => toast.success('已复制到剪贴板'))
    .catch(() => toast.error('复制失败，请手动选择文本复制'))
}

interface ServerConfigCardProps {
  server: ClientDirectMCPServer
  config: CursorMCPServerConfig
  cursorName: string
  onManageDynamicTools: (server: ClientDirectMCPServer) => void
  onManagePrompts: (server: ClientDirectMCPServer) => void
}

function ServerConfigCard({
  server,
  config,
  cursorName,
  onManageDynamicTools,
  onManagePrompts,
}: ServerConfigCardProps): React.JSX.Element {
  const snippet = { [cursorName]: config }
  const snippetJson = JSON.stringify(snippet, null, 2)
  const tools = server.tools ?? []
  const prompts = server.prompts ?? []
  const promptCount = server.prompt_count ?? prompts.length

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Server className="h-5 w-5" />
          {server.name}
        </CardTitle>
        <CardDescription>{server.description}</CardDescription>
        <p className="text-sm text-muted-foreground">
          工具: {server.tool_count} · Prompts: {promptCount} · 传输: Streamable HTTP
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {tools.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium">可用工具</p>
            <TooltipProvider delayDuration={200}>
              <ul className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto rounded-md border bg-muted/30 p-2 text-sm">
                {tools.map((t) => (
                  <li key={t.name}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="cursor-default rounded bg-muted/80 px-2 py-0.5 font-mono text-xs font-medium hover:bg-muted">
                          {t.name}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-xs">
                        {t.description ?? '无描述'}
                      </TooltipContent>
                    </Tooltip>
                  </li>
                ))}
              </ul>
            </TooltipProvider>
          </div>
        )}
        {prompts.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium">可用 Prompts</p>
            <TooltipProvider delayDuration={200}>
              <ul className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto rounded-md border bg-muted/30 p-2 text-sm">
                {prompts.map((p) => (
                  <li key={p.name}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="cursor-default rounded bg-muted/80 px-2 py-0.5 font-mono text-xs font-medium hover:bg-muted">
                          {p.title || p.name}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-xs">
                        {p.description || '无描述'}
                      </TooltipContent>
                    </Tooltip>
                  </li>
                ))}
              </ul>
            </TooltipProvider>
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onManageDynamicTools(server)}
            className="gap-1"
          >
            <Settings2 className="h-4 w-4" />
            管理动态工具
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onManagePrompts(server)}
            className="gap-1"
          >
            <Settings2 className="h-4 w-4" />
            管理 Prompts
          </Button>
        </div>
        <div>
          <p className="mb-2 text-sm font-medium">Cursor mcp.json 配置片段</p>
          <pre className="max-h-48 overflow-auto rounded-md border bg-muted/50 p-3 text-xs">
            <code>{snippetJson}</code>
          </pre>
          <div className="mt-2 flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(snippetJson)}
              className="gap-1"
            >
              <Copy className="h-4 w-4" />
              复制
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] as const

interface AddToolDialogProps {
  serverScope: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

function AddToolDialog({
  serverScope,
  open,
  onOpenChange,
  onSuccess,
}: AddToolDialogProps): React.JSX.Element {
  const [toolKey, setToolKey] = useState('')
  const [description, setDescription] = useState('')
  const [url, setUrl] = useState('')
  const [method, setMethod] = useState<string>('GET')
  const [headersJson, setHeadersJson] = useState('{}')
  const [bodyJson, setBodyJson] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const resetForm = (): void => {
    setToolKey('')
    setDescription('')
    setUrl('')
    setMethod('GET')
    setHeadersJson('{}')
    setBodyJson('')
    setError(null)
  }

  const handleOpenChange = (next: boolean): void => {
    if (!next) resetForm()
    onOpenChange(next)
  }

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    setError(null)
    if (!toolKey.trim()) {
      setError('请填写工具名称')
      return
    }
    if (!url.trim()) {
      setError('请填写请求 URL')
      return
    }
    let headers: Record<string, unknown> = {}
    if (headersJson.trim()) {
      try {
        headers = JSON.parse(headersJson) as Record<string, unknown>
      } catch {
        setError('Headers 必须是合法 JSON')
        return
      }
    }
    let body: unknown = undefined
    if (bodyJson.trim()) {
      try {
        body = JSON.parse(bodyJson)
      } catch {
        setError('Body 必须是合法 JSON')
        return
      }
    }
    const config: Record<string, unknown> = {
      url: url.trim(),
      method: method || 'GET',
      headers,
    }
    if (body !== undefined) config.body = body

    const bodyReq: DynamicToolAddRequest = {
      tool_key: toolKey.trim(),
      tool_type: 'http_call',
      config,
      description: description.trim() || undefined,
    }
    setSubmitting(true)
    try {
      await mcpApi.addDynamicTool(serverScope, bodyReq)
      toast.success('已添加动态工具')
      handleOpenChange(false)
      onSuccess()
    } catch (err) {
      const msg = err instanceof Error ? err.message : '添加失败'
      setError(msg)
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>添加动态工具</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-2">
            <Label htmlFor="add-tool-key">工具名称 (tool_key)</Label>
            <Input
              id="add-tool-key"
              value={toolKey}
              onChange={(e) => setToolKey(e.target.value)}
              placeholder="my_http_tool"
              maxLength={100}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-tool-desc">描述（可选）</Label>
            <Input
              id="add-tool-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="调用指定 HTTP 接口"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-tool-url">URL</Label>
            <Input
              id="add-tool-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://api.example.com/action"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-tool-method">Method</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger id="add-tool-method">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HTTP_METHODS.map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-tool-headers">Headers（可选，JSON）</Label>
            <Textarea
              id="add-tool-headers"
              value={headersJson}
              onChange={(e) => setHeadersJson(e.target.value)}
              placeholder='{"Authorization": "Bearer xxx"}'
              rows={2}
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-tool-body">Body（可选，JSON，POST/PUT/PATCH 时使用）</Label>
            <Textarea
              id="add-tool-body"
              value={bodyJson}
              onChange={(e) => setBodyJson(e.target.value)}
              placeholder='{"key": "value"}'
              rows={3}
              className="font-mono text-sm"
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? '提交中…' : '添加'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function configToFormState(config: Record<string, unknown>): {
  url: string
  method: string
  headersJson: string
  bodyJson: string
} {
  const url = (config.url as string) ?? ''
  const method = ((config.method as string) ?? 'GET').toUpperCase()
  const headers = (config.headers as Record<string, unknown>) ?? {}
  const body = config.body
  return {
    url,
    method: HTTP_METHODS.includes(method as (typeof HTTP_METHODS)[number]) ? method : 'GET',
    headersJson: Object.keys(headers).length ? JSON.stringify(headers, null, 2) : '{}',
    bodyJson:
      body !== undefined && body !== null ? JSON.stringify(body, null, 2) : '',
  }
}

interface EditToolDialogProps {
  serverScope: string
  tool: DynamicToolItem
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

function EditToolDialog({
  serverScope,
  tool,
  open,
  onOpenChange,
  onSuccess,
}: EditToolDialogProps): React.JSX.Element {
  const formState = configToFormState(tool.config ?? {})
  const [description, setDescription] = useState(tool.description ?? '')
  const [url, setUrl] = useState(formState.url)
  const [method, setMethod] = useState(formState.method)
  const [headersJson, setHeadersJson] = useState(formState.headersJson)
  const [bodyJson, setBodyJson] = useState(formState.bodyJson)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      const s = configToFormState(tool.config ?? {})
      setDescription(tool.description ?? '')
      setUrl(s.url)
      setMethod(s.method)
      setHeadersJson(s.headersJson)
      setBodyJson(s.bodyJson)
      setError(null)
    }
  }, [open, tool.id, tool.description, tool.config])

  const handleOpenChange = (next: boolean): void => {
    if (!next) setError(null)
    onOpenChange(next)
  }

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    setError(null)
    if (!url.trim()) {
      setError('请填写请求 URL')
      return
    }
    let headers: Record<string, unknown> = {}
    if (headersJson.trim()) {
      try {
        headers = JSON.parse(headersJson) as Record<string, unknown>
      } catch {
        setError('Headers 必须是合法 JSON')
        return
      }
    }
    let body: unknown = undefined
    if (bodyJson.trim()) {
      try {
        body = JSON.parse(bodyJson)
      } catch {
        setError('Body 必须是合法 JSON')
        return
      }
    }
    const config: Record<string, unknown> = {
      url: url.trim(),
      method: method || 'GET',
      headers,
    }
    if (body !== undefined) config.body = body

    setSubmitting(true)
    try {
      await mcpApi.updateDynamicTool(serverScope, tool.tool_key, {
        tool_type: 'http_call',
        config,
        description: description.trim() || null,
      })
      toast.success('已更新动态工具')
      handleOpenChange(false)
      onSuccess()
    } catch (err) {
      const msg = err instanceof Error ? err.message : '更新失败'
      setError(msg)
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>编辑动态工具</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-2">
            <Label>工具名称 (tool_key)</Label>
            <Input value={tool.tool_key} disabled className="bg-muted font-mono" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-tool-desc">描述（可选）</Label>
            <Input
              id="edit-tool-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="调用指定 HTTP 接口"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-tool-url">URL</Label>
            <Input
              id="edit-tool-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://api.example.com/action"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-tool-method">Method</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger id="edit-tool-method">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HTTP_METHODS.map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-tool-headers">Headers（可选，JSON）</Label>
            <Textarea
              id="edit-tool-headers"
              value={headersJson}
              onChange={(e) => setHeadersJson(e.target.value)}
              placeholder='{"Authorization": "Bearer xxx"}'
              rows={2}
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-tool-body">Body（可选，JSON）</Label>
            <Textarea
              id="edit-tool-body"
              value={bodyJson}
              onChange={(e) => setBodyJson(e.target.value)}
              placeholder='{"key": "value"}'
              rows={3}
              className="font-mono text-sm"
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? '保存中…' : '保存'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// 动态 Prompts：添加 / 编辑对话框、Sheet
// ---------------------------------------------------------------------------

interface AddPromptDialogProps {
  serverScope: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

function AddPromptDialog({
  serverScope,
  open,
  onOpenChange,
  onSuccess,
}: AddPromptDialogProps): React.JSX.Element {
  const [promptKey, setPromptKey] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [template, setTemplate] = useState('')
  const [argumentsJson, setArgumentsJson] = useState('[]')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const resetForm = (): void => {
    setPromptKey('')
    setTitle('')
    setDescription('')
    setTemplate('')
    setArgumentsJson('[]')
    setError(null)
  }

  const handleOpenChange = (next: boolean): void => {
    if (!next) resetForm()
    onOpenChange(next)
  }

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      let args: Record<string, unknown>[] = []
      try {
        args = JSON.parse(argumentsJson) as Record<string, unknown>[]
      } catch {
        setError('arguments_schema 必须是合法 JSON 数组')
        setSubmitting(false)
        return
      }
      await mcpApi.addDynamicPrompt(serverScope, {
        prompt_key: promptKey.trim(),
        template: template.trim(),
        title: title.trim() || undefined,
        description: description.trim() || undefined,
        arguments_schema: args,
      })
      toast.success('已添加 Prompt')
      handleOpenChange(false)
      onSuccess()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '添加失败')
      setError(err instanceof Error ? err.message : '添加失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>添加 Prompt</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="add-prompt-key">Prompt Key（唯一）</Label>
            <Input
              id="add-prompt-key"
              value={promptKey}
              onChange={(e) => setPromptKey(e.target.value)}
              placeholder="e.g. summarize"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-prompt-title">Title（可选）</Label>
            <Input
              id="add-prompt-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="显示名称"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-prompt-desc">Description（可选）</Label>
            <Input
              id="add-prompt-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-prompt-template">Template（占位符 {'{{name}}'}）</Label>
            <Textarea
              id="add-prompt-template"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              placeholder="请总结：{{content}}"
              rows={4}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-prompt-args">Arguments Schema（JSON 数组）</Label>
            <Textarea
              id="add-prompt-args"
              value={argumentsJson}
              onChange={(e) => setArgumentsJson(e.target.value)}
              placeholder='[{"name":"content","description":"要总结的文本","required":true}]'
              rows={3}
              className="font-mono text-sm"
            />
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? '添加中…' : '添加'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

interface EditPromptDialogProps {
  serverScope: string
  tool: DynamicPromptItem
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

function EditPromptDialog({
  serverScope,
  tool,
  open,
  onOpenChange,
  onSuccess,
}: EditPromptDialogProps): React.JSX.Element {
  const [title, setTitle] = useState(tool.title ?? '')
  const [description, setDescription] = useState(tool.description ?? '')
  const [template, setTemplate] = useState(tool.template)
  const [argumentsJson, setArgumentsJson] = useState(
    () => JSON.stringify(tool.arguments_schema ?? [], null, 2)
  )
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setTitle(tool.title ?? '')
      setDescription(tool.description ?? '')
      setTemplate(tool.template)
      setArgumentsJson(JSON.stringify(tool.arguments_schema ?? [], null, 2))
      setError(null)
    }
  }, [open, tool])

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      let args: Record<string, unknown>[] | undefined
      try {
        args = JSON.parse(argumentsJson) as Record<string, unknown>[]
      } catch {
        setError('arguments_schema 必须是合法 JSON 数组')
        setSubmitting(false)
        return
      }
      await mcpApi.updateDynamicPrompt(serverScope, tool.prompt_key, {
        template: template.trim(),
        title: title.trim() || null,
        description: description.trim() || null,
        arguments_schema: args,
      })
      toast.success('已更新 Prompt')
      onOpenChange(false)
      onSuccess()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '更新失败')
      setError(err instanceof Error ? err.message : '更新失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>编辑 Prompt · {tool.prompt_key}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Prompt Key</Label>
            <p className="font-mono text-sm text-muted-foreground">{tool.prompt_key}</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-prompt-title">Title（可选）</Label>
            <Input
              id="edit-prompt-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-prompt-desc">Description（可选）</Label>
            <Input
              id="edit-prompt-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-prompt-template">Template</Label>
            <Textarea
              id="edit-prompt-template"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              rows={4}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-prompt-args">Arguments Schema（JSON 数组）</Label>
            <Textarea
              id="edit-prompt-args"
              value={argumentsJson}
              onChange={(e) => setArgumentsJson(e.target.value)}
              rows={3}
              className="font-mono text-sm"
            />
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? '保存中…' : '保存'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

interface DynamicPromptsSheetProps {
  server: ClientDirectMCPServer
  open: boolean
  onOpenChange: (open: boolean) => void
}

function DynamicPromptsSheet({
  server,
  open,
  onOpenChange,
}: DynamicPromptsSheetProps): React.JSX.Element {
  const queryClient = useQueryClient()
  const currentUser = useUserStore((s) => s.currentUser)
  const isAdmin = currentUser?.role === 'admin'
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [editingPrompt, setEditingPrompt] = useState<DynamicPromptItem | null>(null)

  const { data: prompts = [], isLoading, error } = useQuery({
    queryKey: ['mcp-dynamic-prompts', server.scope],
    queryFn: () => mcpApi.listDynamicPrompts(server.scope),
    enabled: open && isAdmin,
  })

  const deleteMutation = useMutation({
    mutationFn: (promptKey: string) => mcpApi.deleteDynamicPrompt(server.scope, promptKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['mcp-dynamic-prompts', server.scope] })
      void queryClient.invalidateQueries({ queryKey: ['mcp-client-direct-servers'] })
      toast.success('已删除 Prompt')
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : '删除失败')
    },
  })

  const onAddSuccess = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['mcp-dynamic-prompts', server.scope] })
    void queryClient.invalidateQueries({ queryKey: ['mcp-client-direct-servers'] })
  }

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="w-full sm:max-w-md">
          <SheetHeader>
            <SheetTitle>动态 Prompts · {server.name}</SheetTitle>
            <SheetDescription>
              管理该 MCP 服务器上通过配置添加的 Prompt 模板（仅管理员）
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4 flex flex-col gap-4">
            {!isAdmin ? (
              <Alert>
                <AlertDescription>需要管理员权限才能管理 Prompts</AlertDescription>
              </Alert>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-fit gap-1"
                  onClick={() => setAddDialogOpen(true)}
                >
                  <Plus className="h-4 w-4" />
                  添加 Prompt
                </Button>
                {error && (
                  <Alert variant="destructive">
                    <AlertDescription>
                      {error instanceof Error ? error.message : '加载 Prompt 列表失败'}
                    </AlertDescription>
                  </Alert>
                )}
                {isLoading ? (
                  <p className="text-sm text-muted-foreground">加载中…</p>
                ) : prompts.length === 0 ? (
                  <p className="text-sm text-muted-foreground">暂无 Prompt，点击「添加 Prompt」创建</p>
                ) : (
                  <ul className="space-y-2">
                    {prompts.map((p: DynamicPromptItem) => (
                      <li
                        key={p.id}
                        className="flex items-center justify-between gap-2 rounded-md border bg-muted/30 p-3"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="font-mono text-sm font-medium">{p.prompt_key}</p>
                          <p className="truncate text-xs text-muted-foreground">
                            {p.description || p.title || p.template.slice(0, 30)}
                          </p>
                        </div>
                        <div className="flex shrink-0 gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setEditingPrompt(p)}
                            title="编辑"
                          >
                            <Pencil className="h-4 w-4" />
                            <span className="sr-only">编辑</span>
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                            onClick={() => deleteMutation.mutate(p.prompt_key)}
                            disabled={deleteMutation.isPending}
                            title="删除"
                          >
                            <Trash2 className="h-4 w-4" />
                            <span className="sr-only">删除</span>
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        </SheetContent>
      </Sheet>
      <AddPromptDialog
        serverScope={server.scope}
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        onSuccess={onAddSuccess}
      />
      {editingPrompt ? (
        <EditPromptDialog
          key={editingPrompt.id}
          serverScope={server.scope}
          tool={editingPrompt}
          open={!!editingPrompt}
          onOpenChange={(open) => !open && setEditingPrompt(null)}
          onSuccess={onAddSuccess}
        />
      ) : null}
    </>
  )
}

interface DynamicToolsSheetProps {
  server: ClientDirectMCPServer
  open: boolean
  onOpenChange: (open: boolean) => void
}

function DynamicToolsSheet({
  server,
  open,
  onOpenChange,
}: DynamicToolsSheetProps): React.JSX.Element {
  const queryClient = useQueryClient()
  const currentUser = useUserStore((s) => s.currentUser)
  const isAdmin = currentUser?.role === 'admin'
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [editingTool, setEditingTool] = useState<DynamicToolItem | null>(null)

  const { data: tools = [], isLoading, error } = useQuery({
    queryKey: ['mcp-dynamic-tools', server.scope],
    queryFn: () => mcpApi.listDynamicTools(server.scope),
    enabled: open && isAdmin,
  })

  const deleteMutation = useMutation({
    mutationFn: (toolKey: string) => mcpApi.deleteDynamicTool(server.scope, toolKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['mcp-dynamic-tools', server.scope] })
      void queryClient.invalidateQueries({ queryKey: ['mcp-client-direct-servers'] })
      toast.success('已删除动态工具')
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : '删除失败')
    },
  })

  const onAddSuccess = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['mcp-dynamic-tools', server.scope] })
    void queryClient.invalidateQueries({ queryKey: ['mcp-client-direct-servers'] })
  }

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="w-full sm:max-w-md">
          <SheetHeader>
            <SheetTitle>动态工具 · {server.name}</SheetTitle>
            <SheetDescription>
              管理该 MCP 服务器上通过配置添加的动态工具（仅管理员）
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4 flex flex-col gap-4">
            {!isAdmin ? (
              <Alert>
                <AlertDescription>需要管理员权限才能管理动态工具</AlertDescription>
              </Alert>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-fit gap-1"
                  onClick={() => setAddDialogOpen(true)}
                >
                  <Plus className="h-4 w-4" />
                  添加工具
                </Button>
                {error && (
                  <Alert variant="destructive">
                    <AlertDescription>
                      {error instanceof Error ? error.message : '加载动态工具列表失败'}
                    </AlertDescription>
                  </Alert>
                )}
                {isLoading ? (
                  <p className="text-sm text-muted-foreground">加载中…</p>
                ) : tools.length === 0 ? (
                  <p className="text-sm text-muted-foreground">暂无动态工具，点击「添加工具」创建</p>
                ) : (
              <ul className="space-y-2">
                {tools.map((t: DynamicToolItem) => (
                  <li
                    key={t.id}
                    className="flex items-center justify-between gap-2 rounded-md border bg-muted/30 p-3"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-mono text-sm font-medium">{t.tool_key}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {t.description || t.tool_type}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setEditingTool(t)}
                        title="编辑"
                      >
                        <Pencil className="h-4 w-4" />
                        <span className="sr-only">编辑</span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive hover:text-destructive"
                        onClick={() => deleteMutation.mutate(t.tool_key)}
                        disabled={deleteMutation.isPending}
                        title="删除"
                      >
                        <Trash2 className="h-4 w-4" />
                        <span className="sr-only">删除</span>
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
                )}
              </>
            )}
          </div>
        </SheetContent>
      </Sheet>
      <AddToolDialog
        serverScope={server.scope}
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        onSuccess={onAddSuccess}
      />
      {editingTool ? (
        <EditToolDialog
          key={editingTool.id}
          serverScope={server.scope}
          tool={editingTool}
          open={!!editingTool}
          onOpenChange={(open) => !open && setEditingTool(null)}
          onSuccess={onAddSuccess}
        />
      ) : null}
    </>
  )
}

export default function SystemMCPPage(): React.JSX.Element {
  const [dynamicToolsServer, setDynamicToolsServer] =
    useState<ClientDirectMCPServer | null>(null)
  const [dynamicPromptsServer, setDynamicPromptsServer] =
    useState<ClientDirectMCPServer | null>(null)

  const {
    data: listData,
    isLoading: listLoading,
    error: listError,
  } = useQuery({
    queryKey: ['mcp-client-direct-servers'],
    queryFn: () => mcpApi.listClientDirectServers(),
  })

  const { data: configData } = useQuery({
    queryKey: ['mcp-client-config'],
    queryFn: () => mcpApi.getClientConfig(),
  })

  const servers = listData?.servers ?? []
  const mcpServers = (configData as ClientMCPConfigResponse | undefined)?.mcpServers ?? {}

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">系统 MCP（客户端直连）</h1>
        <p className="mt-2 text-muted-foreground">
          由平台暴露的 Streamable HTTP MCP 服务，Cursor 等客户端可通过 mcp.json 直连并调用工具。
        </p>
      </div>

      <Alert className="mb-6">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          将下方配置填入 <code className="rounded bg-muted px-1">~/.cursor/mcp.json</code> 或项目
          <code className="rounded bg-muted px-1">.cursor/mcp.json</code>
          ，并将 <code className="rounded bg-muted px-1">&lt;YOUR_API_KEY&gt;</code> 替换为具有
          <code className="rounded bg-muted px-1">mcp:llm-server</code> 权限的 API Key。
        </AlertDescription>
      </Alert>

      {listError && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>加载系统 MCP 列表失败，请稍后重试</AlertDescription>
        </Alert>
      )}

      {listLoading ? (
        <div className="flex justify-center py-12 text-muted-foreground">加载中...</div>
      ) : servers.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
          <Server className="mb-4 h-12 w-12 text-muted-foreground" />
          <p className="text-muted-foreground">暂无客户端直连的 MCP 服务</p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {servers.map((server) => {
              const cursorName = scopeToCursorName(server.scope)
              const config = mcpServers[cursorName]
              if (!config) return null
              return (
                <ServerConfigCard
                  key={server.scope}
                  server={server}
                  config={config}
                  cursorName={cursorName}
                  onManageDynamicTools={setDynamicToolsServer}
                  onManagePrompts={setDynamicPromptsServer}
                />
              )
            })}
          </div>
        </>
      )}

      {dynamicToolsServer && (
        <DynamicToolsSheet
          server={dynamicToolsServer}
          open={!!dynamicToolsServer}
          onOpenChange={(open) => !open && setDynamicToolsServer(null)}
        />
      )}
      {dynamicPromptsServer && (
        <DynamicPromptsSheet
          server={dynamicPromptsServer}
          open={!!dynamicPromptsServer}
          onOpenChange={(open) => !open && setDynamicPromptsServer(null)}
        />
      )}
    </div>
  )
}
