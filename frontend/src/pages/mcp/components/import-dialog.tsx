/**
 * MCP 服务器导入对话框组件（占位实现，待后续完善）
 */

import { useState } from 'react'

import { Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface ImportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ImportDialog({ open, onOpenChange }: ImportDialogProps): React.JSX.Element {
  const [activeTab, setActiveTab] = useState<'templates' | 'custom'>('templates')
  const [isLoading, setIsLoading] = useState(false)

  const handleImport = (): void => {
    setIsLoading(true)
    // TODO: 实现导入逻辑
    setTimeout(() => {
      setIsLoading(false)
      onOpenChange(false)
    }, 1000)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>添加 MCP 服务器</DialogTitle>
          <DialogDescription>从模板库选择或手动配置 MCP 服务器</DialogDescription>
        </DialogHeader>

        <Tabs
          value={activeTab}
          onValueChange={(v) => {
            setActiveTab(v as 'templates' | 'custom')
          }}
        >
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="templates">模板库</TabsTrigger>
            <TabsTrigger value="custom">自定义</TabsTrigger>
          </TabsList>

          <TabsContent value="templates" className="mt-4">
            <ScrollArea className="h-[400px] pr-4">
              <div className="space-y-3">
                {/* 占位模板列表 */}
                <div className="rounded-lg border p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold">Filesystem MCP</h4>
                      <p className="mt-1 text-sm text-muted-foreground">
                        安全地访问本地文件系统，支持文件读写、目录操作等功能
                      </p>
                      <div className="mt-2 flex gap-2">
                        <Badge variant="secondary" className="text-xs">
                          文件
                        </Badge>
                        <Badge variant="secondary" className="text-xs">
                          系统
                        </Badge>
                      </div>
                    </div>
                    <Button size="sm">添加</Button>
                  </div>
                </div>

                <div className="rounded-lg border p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold">Database MCP</h4>
                      <p className="mt-1 text-sm text-muted-foreground">
                        支持多种数据库的 SQL 查询和数据库管理功能
                      </p>
                      <div className="mt-2 flex gap-2">
                        <Badge variant="secondary" className="text-xs">
                          数据库
                        </Badge>
                        <Badge variant="secondary" className="text-xs">
                          SQL
                        </Badge>
                      </div>
                    </div>
                    <Button size="sm">添加</Button>
                  </div>
                </div>

                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <span className="text-sm">更多模板即将推出...</span>
                </div>
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="custom" className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="server-name">服务器名称</Label>
              <Input id="server-name" placeholder="输入服务器名称" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="server-url">服务器 URL</Label>
              <Input id="server-url" placeholder="stdio://python 或 http://localhost:3000" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="env-type">环境类型</Label>
              <Input id="env-type" value="dynamic_injected" disabled />
            </div>

            <div className="flex justify-end gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  onOpenChange(false)
                }}
              >
                取消
              </Button>
              <Button onClick={handleImport} disabled={isLoading}>
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                添加
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
