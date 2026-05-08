/**
 * MCP 服务器管理页面
 */

import { useMemo, useState } from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Plus, Search, Server } from 'lucide-react'
import { toast } from 'sonner'

import { mcpApi } from '@/api/mcp'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { MCPServerConfig } from '@/types/mcp'

import { EditDialog } from './components/edit-dialog'
import { ImportDialog } from './components/import-dialog'
import { MCPServerCard } from './components/server-card'

export default function MCPPage(): React.JSX.Element {
  const [searchQuery, setSearchQuery] = useState('')
  const [importDialogOpen, setImportDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [serverToEdit, setServerToEdit] = useState<MCPServerConfig | null>(null)
  const [selectedServer, setSelectedServer] = useState<MCPServerConfig | null>(null)

  const queryClient = useQueryClient()

  const {
    data: serversData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => mcpApi.listServers(),
  })

  // 切换服务器启用状态
  const toggleServerMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      mcpApi.toggleServer(id, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
      toast.success('服务器状态已更新')
    },
    onError: (error: Error) => {
      toast.error(`操作失败: ${error.message}`)
    },
  })

  // 删除服务器
  const deleteServerMutation = useMutation({
    mutationFn: (id: string) => mcpApi.deleteServer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
      toast.success('服务器已删除')
      setSelectedServer(null)
    },
    onError: (error: Error) => {
      toast.error(`删除失败: ${error.message}`)
    },
  })

  const allServers = useMemo(
    () => [...(serversData?.system_servers ?? []), ...(serversData?.user_servers ?? [])],
    [serversData]
  )

  const filteredServers = useMemo(() => {
    return allServers.filter((server) => {
      const query = searchQuery.toLowerCase()
      const name = (server.display_name ?? server.name).toLowerCase()
      const url = server.url.toLowerCase()
      return name.includes(query) || url.includes(query)
    })
  }, [allServers, searchQuery])

  return (
    <div className="container mx-auto p-6">
      {/* 页面头部 */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">MCP 服务器</h1>
          <p className="mt-2 text-muted-foreground">管理和配置 MCP 服务器</p>
        </div>
        <Button
          onClick={() => {
            setImportDialogOpen(true)
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          添加服务器
        </Button>
      </div>

      {/* 搜索栏 */}
      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索服务器..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
            }}
            className="pl-10"
          />
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>加载服务器列表失败，请稍后重试</AlertDescription>
        </Alert>
      )}

      {/* 服务器列表 */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <span className="text-muted-foreground">加载中...</span>
        </div>
      ) : filteredServers.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
          <Server className="mb-4 h-12 w-12 text-muted-foreground" />
          <p className="text-muted-foreground">
            {searchQuery ? '没有找到匹配的服务器' : '暂无 MCP 服务器'}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            点击上方按钮添加您的第一个 MCP 服务器
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredServers.map((server) => {
            const isSelected = selectedServer?.id === server.id
            return (
              <MCPServerCard
                key={server.id}
                server={server}
                selected={isSelected}
                className={isSelected ? 'md:col-span-2 lg:col-span-3' : ''}
                onClick={(s) => {
                  setSelectedServer((prev) => (prev?.id === s.id ? null : s))
                }}
                onToggle={(s, enabled) => {
                  toggleServerMutation.mutate({ id: s.id, enabled })
                }}
                onEdit={(s) => {
                  setServerToEdit(s)
                  setEditDialogOpen(true)
                }}
                onDelete={(s) => {
                  if (confirm(`确定要删除服务器 "${s.display_name ?? s.name}" 吗？`)) {
                    deleteServerMutation.mutate(s.id)
                    setSelectedServer(null)
                  }
                }}
              />
            )
          })}
        </div>
      )}

      <ImportDialog open={importDialogOpen} onOpenChange={setImportDialogOpen} />

      <EditDialog
        server={serverToEdit}
        open={editDialogOpen}
        onOpenChange={(open) => {
          setEditDialogOpen(open)
          if (!open) setServerToEdit(null)
        }}
      />
    </div>
  )
}
