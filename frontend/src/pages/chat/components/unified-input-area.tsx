/**
 * 统一输入区 - 聊天页底部「对话 | 视频」模式切换
 * 始终显示切换栏；无 session 时选视频则先建会话再创建任务
 */

import type React from 'react'

import { MessageSquare, Video } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import type { VideoModel, VideoDuration } from '@/types/video-task'

import VideoTaskCreateFormCompact from '@/pages/video-tasks/components/create-form-compact'

import ChatInput from './chat-input'

export type UnifiedInputMode = 'chat' | 'video'

/** 无 session 时创建视频任务的参数（由父组件先建会话再调 API） */
export interface VideoCreateParams {
  promptText: string
  model: VideoModel
  duration: VideoDuration
  referenceImages: string[]
}

export interface UnifiedInputAreaProps {
  /** 当前模式 */
  mode: UnifiedInputMode
  onModeChange: (mode: UnifiedInputMode) => void
  /** 当前会话 ID（无则处于新建对话） */
  sessionId: string | undefined
  /** 对话模式：输入与发送 */
  chatValue: string
  chatOnChange: (value: string) => void
  chatOnSend: () => void
  chatIsLoading: boolean
  /** 工具栏左侧额外（如对话工具按钮） */
  toolbarLeftExtra?: React.ReactNode
  /** 视频模式：有 session 时创建成功 / 无权限回调 */
  onVideoTaskCreated?: () => void
  onVideoSessionForbidden?: () => void
  /** 无 session 时用户点创建：父组件先建会话再创建任务后调用 onVideoTaskCreated 或导航 */
  onVideoCreateWithoutSession?: (params: VideoCreateParams) => Promise<void>
}

export default function UnifiedInputArea({
  mode,
  onModeChange,
  sessionId,
  chatValue,
  chatOnChange,
  chatOnSend,
  chatIsLoading,
  toolbarLeftExtra,
  onVideoTaskCreated,
  onVideoSessionForbidden,
  onVideoCreateWithoutSession,
}: Readonly<UnifiedInputAreaProps>): React.JSX.Element {
  const isChat = mode === 'chat'
  const isVideo = mode === 'video'
  const inputContent = isChat ? (
    <ChatInput
      value={chatValue}
      onChange={chatOnChange}
      onSend={chatOnSend}
      isLoading={chatIsLoading}
      toolbarLeftExtra={toolbarLeftExtra}
    />
  ) : isVideo ? (
    <VideoTaskCreateFormCompact
      sessionId={sessionId}
      onTaskCreated={onVideoTaskCreated}
      onSessionForbidden={onVideoSessionForbidden}
      onVideoCreateWithoutSession={onVideoCreateWithoutSession}
      disabled={chatIsLoading}
    />
  ) : null;

  return (
    <div className="space-y-2">
      <div className="flex justify-center gap-0.5 rounded-full bg-muted/40 p-0.5">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onModeChange('chat')}
          className={cn(
            'h-7 rounded-full px-3 text-xs font-medium',
            isChat
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <MessageSquare className="mr-1.5 h-3.5 w-3.5" />
          对话
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onModeChange('video')}
          className={cn(
            'h-7 rounded-full px-3 text-xs font-medium',
            isVideo
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <Video className="mr-1.5 h-3.5 w-3.5" />
          视频
        </Button>
      </div>
      {isVideo && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => onModeChange('chat')}
            className="text-xs text-muted-foreground/70 underline-offset-2 hover:text-foreground hover:underline"
          >
            切回对话
          </button>
        </div>
      )}
      {inputContent}
    </div>
  )
}
