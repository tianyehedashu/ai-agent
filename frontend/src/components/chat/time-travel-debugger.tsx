/**
 * Time Travel Debugger - 时间旅行调试组件
 *
 * 提供检查点可视化和状态回溯功能
 */

import { useState, useEffect, useCallback } from 'react'

import { Clock, GitBranch, RotateCcw, Diff, Eye, History, X } from 'lucide-react'

import { chatApi } from '@/api/chat'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import type { Checkpoint, CheckpointDiff } from '@/types'

interface CheckpointState {
  sessionId: string
  messages: Array<{
    role: string
    content: string
  }>
  iteration: number
  totalTokens: number
  pendingToolCall?: {
    name: string
    arguments: Record<string, unknown>
  }
  completed: boolean
}

interface TimeTravelDebuggerProps {
  sessionId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onRestore?: (checkpointId: string) => void
}

export function TimeTravelDebugger({
  sessionId,
  open,
  onOpenChange,
  onRestore,
}: Readonly<TimeTravelDebuggerProps>): React.JSX.Element {
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([])
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<Checkpoint | null>(null)
  const [checkpointState, setCheckpointState] = useState<CheckpointState | null>(null)
  const [compareCheckpoint, setCompareCheckpoint] = useState<Checkpoint | null>(null)
  const [diff, setDiff] = useState<CheckpointDiff | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())

  // 加载检查点列表
  const loadCheckpoints = useCallback(async () => {
    if (!sessionId) return

    setIsLoading(true)
    try {
      const data = await chatApi.getCheckpoints(sessionId)
      setCheckpoints(data)
      if (data.length > 0) {
        setSelectedCheckpoint(data[0])
      }
    } catch (error) {
      console.error('Failed to load checkpoints:', error)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  // 加载检查点状态
  const loadCheckpointState = useCallback(async (checkpointId: string) => {
    setIsLoading(true)
    try {
      const state = await chatApi.getCheckpointState(checkpointId)
      setCheckpointState(state as unknown as CheckpointState)
    } catch (error) {
      console.error('Failed to load checkpoint state:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  // 对比两个检查点
  const compareTwoCheckpoints = useCallback(async (id1: string, id2: string) => {
    setIsLoading(true)
    try {
      const diffResult = await chatApi.diffCheckpoints(id1, id2)
      setDiff(diffResult)
    } catch (error) {
      console.error('Failed to compare checkpoints:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  // 监听打开状态
  useEffect(() => {
    if (open && sessionId) {
      void loadCheckpoints()
    }
  }, [open, sessionId, loadCheckpoints])

  // 监听选中检查点
  useEffect(() => {
    if (selectedCheckpoint) {
      void loadCheckpointState(selectedCheckpoint.id)
    }
  }, [selectedCheckpoint, loadCheckpointState])

  // 监听对比检查点
  useEffect(() => {
    if (selectedCheckpoint && compareCheckpoint) {
      void compareTwoCheckpoints(selectedCheckpoint.id, compareCheckpoint.id)
    } else {
      setDiff(null)
    }
  }, [selectedCheckpoint, compareCheckpoint, compareTwoCheckpoints])

  // 切换展开/折叠
  const toggleExpanded = (id: string): void => {
    const newExpanded = new Set(expandedItems)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedItems(newExpanded)
  }

  // 格式化时间
  const formatTime = (dateStr: string): string => {
    const date = new Date(dateStr)
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  // 恢复到检查点
  const handleRestore = (checkpoint: Checkpoint): void => {
    if (onRestore) {
      onRestore(checkpoint.id)
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[80vh] max-w-4xl flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            时间旅行调试
          </DialogTitle>
          <DialogDescription>查看会话执行历史，对比状态变化，恢复到任意检查点</DialogDescription>
        </DialogHeader>

        <div className="flex flex-1 gap-4 overflow-hidden">
          {/* 左侧 - 检查点时间线 */}
          <div className="w-72 shrink-0 border-r pr-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-medium">检查点历史</h3>
              <Button variant="ghost" size="sm" onClick={loadCheckpoints} disabled={isLoading}>
                <RotateCcw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
              </Button>
            </div>

            <ScrollArea className="h-[calc(100%-40px)]">
              <div className="relative space-y-1">
                {/* 时间线 */}
                <div className="absolute bottom-0 left-3 top-0 w-0.5 bg-border" />

                {checkpoints.map((checkpoint) => (
                  <button
                    type="button"
                    key={checkpoint.id}
                    className={cn(
                      'relative w-full cursor-pointer rounded py-2 pl-8 pr-2 text-left transition-colors',
                      selectedCheckpoint?.id === checkpoint.id
                        ? 'bg-primary/10'
                        : 'hover:bg-muted/50'
                    )}
                    onClick={() => {
                      setSelectedCheckpoint(checkpoint)
                    }}
                  >
                    {/* 时间线节点 */}
                    <div
                      className={cn(
                        'absolute left-1.5 top-3 h-3 w-3 rounded-full border-2',
                        selectedCheckpoint?.id === checkpoint.id
                          ? 'border-primary bg-primary'
                          : 'border-border bg-background'
                      )}
                    />

                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          {formatTime(checkpoint.createdAt)}
                        </div>
                        <div className="mt-0.5 text-sm font-medium">Step {checkpoint.step}</div>
                      </div>

                      {/* 对比复选框 */}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={(e) => {
                          e.stopPropagation()
                          setCompareCheckpoint(
                            compareCheckpoint?.id === checkpoint.id ? null : checkpoint
                          )
                        }}
                      >
                        <Diff
                          className={cn(
                            'h-3 w-3',
                            compareCheckpoint?.id === checkpoint.id && 'text-primary'
                          )}
                        />
                      </Button>
                    </div>
                  </button>
                ))}

                {checkpoints.length === 0 && !isLoading && (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    暂无检查点记录
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>

          {/* 右侧 - 状态详情 */}
          <div className="flex-1 overflow-hidden">
            <Tabs defaultValue="state" className="flex h-full flex-col">
              <TabsList className="shrink-0">
                <TabsTrigger value="state" className="flex items-center gap-1">
                  <Eye className="h-3 w-3" />
                  状态
                </TabsTrigger>
                <TabsTrigger value="messages" className="flex items-center gap-1">
                  <GitBranch className="h-3 w-3" />
                  消息
                </TabsTrigger>
                {diff && (
                  <TabsTrigger value="diff" className="flex items-center gap-1">
                    <Diff className="h-3 w-3" />
                    对比
                  </TabsTrigger>
                )}
              </TabsList>

              {/* 状态 Tab */}
              <TabsContent value="state" className="mt-4 flex-1 overflow-auto">
                {checkpointState ? (
                  <div className="space-y-4">
                    {/* 基本信息 */}
                    <div className="grid grid-cols-3 gap-4">
                      <div className="rounded-lg border p-3">
                        <div className="text-xs text-muted-foreground">迭代次数</div>
                        <div className="text-2xl font-bold">{checkpointState.iteration}</div>
                      </div>
                      <div className="rounded-lg border p-3">
                        <div className="text-xs text-muted-foreground">消耗 Token</div>
                        <div className="text-2xl font-bold">
                          {checkpointState.totalTokens.toLocaleString()}
                        </div>
                      </div>
                      <div className="rounded-lg border p-3">
                        <div className="text-xs text-muted-foreground">状态</div>
                        <div className="mt-1 flex items-center gap-2">
                          {checkpointState.completed && (
                            <Badge variant="secondary" className="bg-green-500/10 text-green-600">
                              已完成
                            </Badge>
                          )}
                          {!checkpointState.completed && checkpointState.pendingToolCall && (
                            <Badge variant="secondary" className="bg-yellow-500/10 text-yellow-600">
                              等待确认
                            </Badge>
                          )}
                          {!checkpointState.completed && !checkpointState.pendingToolCall && (
                            <Badge variant="secondary" className="bg-blue-500/10 text-blue-600">
                              执行中
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* 待执行工具 */}
                    {checkpointState.pendingToolCall && (
                      <div className="rounded-lg border p-4">
                        <div className="mb-2 flex items-center justify-between">
                          <h4 className="text-sm font-medium">待执行工具</h4>
                          <Badge variant="outline">{checkpointState.pendingToolCall.name}</Badge>
                        </div>
                        <pre className="overflow-auto rounded bg-muted p-3 text-xs">
                          {JSON.stringify(checkpointState.pendingToolCall.arguments, null, 2)}
                        </pre>
                      </div>
                    )}

                    {/* 操作按钮 */}
                    {selectedCheckpoint && (
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          onClick={() => {
                            handleRestore(selectedCheckpoint)
                          }}
                        >
                          <RotateCcw className="mr-2 h-4 w-4" />
                          从此处恢复执行
                        </Button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground">
                    选择一个检查点查看状态
                  </div>
                )}
              </TabsContent>

              {/* 消息 Tab */}
              <TabsContent value="messages" className="mt-4 flex-1 overflow-auto">
                {checkpointState?.messages ? (
                  <div className="space-y-2">
                    {checkpointState.messages.map((msg, index) => {
                      const messageId = `msg-${msg.role}-${String(index)}`
                      const isExpanded = expandedItems.has(messageId)
                      const truncatedContent =
                        msg.content.length > 200 ? `${msg.content.slice(0, 200)}...` : msg.content

                      return (
                        <div
                          key={messageId}
                          className={cn(
                            'rounded-lg border p-3',
                            msg.role === 'user' && 'bg-primary/5',
                            msg.role === 'assistant' && 'bg-muted/50',
                            msg.role === 'tool' && 'bg-blue-500/5'
                          )}
                        >
                          <div className="mb-1 flex items-center gap-2">
                            <Badge variant="outline" className="text-xs">
                              {msg.role}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              #{String(index + 1)}
                            </span>
                          </div>
                          <button
                            type="button"
                            className="w-full cursor-pointer whitespace-pre-wrap text-left text-sm"
                            onClick={() => {
                              toggleExpanded(messageId)
                            }}
                          >
                            {isExpanded ? msg.content : truncatedContent}
                          </button>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground">
                    选择一个检查点查看消息
                  </div>
                )}
              </TabsContent>

              {/* 对比 Tab */}
              {diff && (
                <TabsContent value="diff" className="mt-4 flex-1 overflow-auto">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">
                        对比: Step {selectedCheckpoint?.step} → Step {compareCheckpoint?.step}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setCompareCheckpoint(null)
                        }}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                      <div className="rounded-lg border p-3">
                        <div className="text-xs text-muted-foreground">新增消息</div>
                        <div className="text-2xl font-bold text-green-600">
                          +{diff.messagesAdded}
                        </div>
                      </div>
                      <div className="rounded-lg border p-3">
                        <div className="text-xs text-muted-foreground">Token 变化</div>
                        <div
                          className={cn(
                            'text-2xl font-bold',
                            diff.tokensDelta > 0 ? 'text-red-600' : 'text-green-600'
                          )}
                        >
                          {diff.tokensDelta > 0 ? '+' : ''}
                          {diff.tokensDelta.toLocaleString()}
                        </div>
                      </div>
                      <div className="rounded-lg border p-3">
                        <div className="text-xs text-muted-foreground">迭代变化</div>
                        <div className="text-2xl font-bold text-blue-600">
                          +{diff.iterationDelta}
                        </div>
                      </div>
                    </div>
                  </div>
                </TabsContent>
              )}
            </Tabs>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
