import { useState } from 'react'

import { Sparkles, Loader2 } from 'lucide-react'

import { sessionApi } from '@/api/session'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useToast } from '@/hooks/use-toast'

interface EditTitleDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sessionId: string
  currentTitle: string | undefined
  onSuccess?: () => void
}

export function EditTitleDialog({
  open,
  onOpenChange,
  sessionId,
  currentTitle,
  onSuccess,
}: Readonly<EditTitleDialogProps>): React.JSX.Element {
  const [title, setTitle] = useState(currentTitle ?? '')
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const { toast } = useToast()

  const handleGenerate = async (strategy: 'first_message' | 'summary'): Promise<void> => {
    setIsGenerating(true)
    try {
      const updated = await sessionApi.generateTitle(sessionId, strategy)
      setTitle(updated.title ?? '')
      toast({
        title: '标题生成成功',
        description: '已根据对话内容生成新标题',
      })
      onSuccess?.()
    } catch (error) {
      toast({
        variant: 'destructive',
        title: '生成失败',
        description: error instanceof Error ? error.message : '未知错误',
      })
    } finally {
      setIsGenerating(false)
    }
  }

  const handleSave = async (): Promise<void> => {
    if (!title.trim()) {
      toast({
        variant: 'destructive',
        title: '标题不能为空',
      })
      return
    }

    setIsSaving(true)
    try {
      await sessionApi.update(sessionId, { title: title.trim() })
      toast({
        title: '保存成功',
        description: '标题已更新',
      })
      onSuccess?.()
      onOpenChange(false)
    } catch (error) {
      toast({
        variant: 'destructive',
        title: '保存失败',
        description: error instanceof Error ? error.message : '未知错误',
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>编辑会话标题</DialogTitle>
          <DialogDescription>修改或生成会话标题，让对话更容易识别</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="title">标题</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value)
              }}
              placeholder="输入标题..."
              maxLength={200}
            />
            <p className="text-xs text-muted-foreground">{title.length}/200 字符</p>
          </div>

          <div className="space-y-2">
            <Label>智能生成</Label>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => handleGenerate('summary')}
                disabled={isGenerating}
              >
                {isGenerating ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                总结生成
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => handleGenerate('first_message')}
                disabled={isGenerating}
              >
                {isGenerating ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                首句生成
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              总结生成：根据多条消息总结生成标题
              <br />
              首句生成：根据第一条消息生成标题
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button onClick={handleSave} disabled={isSaving || !title.trim()}>
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                保存中...
              </>
            ) : (
              '保存'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
