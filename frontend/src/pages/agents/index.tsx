import { useState } from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Bot, MoreVertical, Pencil, Trash2 } from 'lucide-react'

import { agentApi } from '@/api/agent'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { Agent } from '@/types'

import AgentDialog from './components/agent-dialog'

export default function AgentsPage(): React.JSX.Element {
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null)
  const queryClient = useQueryClient()

  const { data: agentsData, isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentApi.list(1, 50),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => agentApi.delete(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['agents'] })
    },
  })

  const agents = agentsData?.items ?? []

  const handleEdit = (agent: Agent): void => {
    setEditingAgent(agent)
    setIsDialogOpen(true)
  }

  const handleDelete = (agent: Agent): void => {
    if (confirm(`确定要删除 Agent "${agent.name}" 吗？`)) {
      void deleteMutation.mutateAsync(agent.id)
    }
  }

  const handleDialogClose = (): void => {
    setIsDialogOpen(false)
    setEditingAgent(null)
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agents</h1>
          <p className="text-muted-foreground">管理您的 AI Agents</p>
        </div>
        <Button
          onClick={() => {
            setIsDialogOpen(true)
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          创建 Agent
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-6 w-1/2 rounded bg-muted" />
                <div className="mt-2 h-4 w-3/4 rounded bg-muted" />
              </CardHeader>
              <CardContent>
                <div className="h-4 w-full rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : agents.length === 0 ? (
        <Card className="p-12">
          <div className="flex flex-col items-center justify-center text-center">
            <Bot className="mb-4 h-16 w-16 text-muted-foreground/50" />
            <h3 className="mb-2 text-lg font-semibold">暂无 Agent</h3>
            <p className="mb-4 text-muted-foreground">创建您的第一个 AI Agent 来开始使用</p>
            <Button
              onClick={() => {
                setIsDialogOpen(true)
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              创建 Agent
            </Button>
          </div>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onEdit={() => {
                handleEdit(agent)
              }}
              onDelete={() => {
                handleDelete(agent)
              }}
            />
          ))}
        </div>
      )}

      <AgentDialog open={isDialogOpen} onOpenChange={handleDialogClose} agent={editingAgent} />
    </div>
  )
}

function AgentCard({
  agent,
  onEdit,
  onDelete,
}: {
  agent: Agent
  onEdit: () => void
  onDelete: () => void
}): React.JSX.Element {
  return (
    <Card className="group relative">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Bot className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">{agent.name}</CardTitle>
              <CardDescription className="text-xs">{agent.model}</CardDescription>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={onEdit}>
                <Pencil className="mr-2 h-4 w-4" />
                编辑
              </DropdownMenuItem>
              <DropdownMenuItem className="text-destructive" onClick={onDelete}>
                <Trash2 className="mr-2 h-4 w-4" />
                删除
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent>
        <p className="mb-4 line-clamp-2 text-sm text-muted-foreground">
          {agent.description ?? '暂无描述'}
        </p>
        <div className="flex flex-wrap gap-1">
          {agent.tools.slice(0, 3).map((tool) => (
            <Badge key={tool} variant="secondary" className="text-xs">
              {tool}
            </Badge>
          ))}
          {agent.tools.length > 3 && (
            <Badge variant="secondary" className="text-xs">
              +{agent.tools.length - 3}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
