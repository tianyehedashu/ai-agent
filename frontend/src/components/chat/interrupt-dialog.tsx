/**
 * Interrupt Dialog - 中断确认对话框
 *
 * Human-in-the-Loop 功能的核心 UI
 */

import { useState } from 'react'

import { AlertTriangle, Check, X, Edit } from 'lucide-react'

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { ToolCall } from '@/types'

interface InterruptDialogProps {
  open: boolean
  pendingAction: ToolCall
  reason: string
  onApprove: () => void
  onReject: () => void
  onModify: (modifiedArgs: Record<string, unknown>) => void
}

export function InterruptDialog({
  open,
  pendingAction,
  reason,
  onApprove,
  onReject,
  onModify,
}: Readonly<InterruptDialogProps>): React.JSX.Element {
  const [isEditing, setIsEditing] = useState(false)
  const [editedArgs, setEditedArgs] = useState(JSON.stringify(pendingAction.arguments, null, 2))

  const handleModify = (): void => {
    try {
      const args = JSON.parse(editedArgs) as Record<string, unknown>
      onModify(args)
    } catch {
      // JSON 解析错误
      alert('参数格式错误，请检查 JSON 语法')
    }
  }

  return (
    <AlertDialog open={open}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-yellow-500" />
            需要确认操作
          </AlertDialogTitle>
          <AlertDialogDescription>{reason}</AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-4 py-4">
          {/* 工具信息 */}
          <div>
            <Label className="text-sm font-medium">工具</Label>
            <p className="mt-1 font-mono text-sm text-primary">{pendingAction.name}</p>
          </div>

          {/* 参数 */}
          <div>
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">参数</Label>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsEditing(!isEditing)
                }}
              >
                <Edit className="mr-1 h-3 w-3" />
                {isEditing ? '取消编辑' : '编辑'}
              </Button>
            </div>

            {isEditing ? (
              <Textarea
                value={editedArgs}
                onChange={(e) => {
                  setEditedArgs(e.target.value)
                }}
                className="mt-2 h-32 font-mono text-sm"
              />
            ) : (
              <pre className="mt-2 overflow-x-auto rounded-lg bg-muted p-3 font-mono text-sm">
                {JSON.stringify(pendingAction.arguments, null, 2)}
              </pre>
            )}
          </div>
        </div>

        <AlertDialogFooter className="flex-col gap-2 sm:flex-row">
          <Button variant="outline" onClick={onReject} className="flex items-center gap-2">
            <X className="h-4 w-4" />
            拒绝
          </Button>

          {isEditing && (
            <Button variant="secondary" onClick={handleModify} className="flex items-center gap-2">
              <Edit className="h-4 w-4" />
              使用修改后的参数执行
            </Button>
          )}

          <Button onClick={onApprove} className="flex items-center gap-2">
            <Check className="h-4 w-4" />
            批准执行
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
