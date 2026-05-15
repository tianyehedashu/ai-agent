/**
 * 统一输入区 - 聊天页底部「对话 | 生图 | 视频」模式切换
 * 始终显示切换栏；无 session 时选视频则先建会话再创建任务
 */

import type React from 'react'
import { useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { ImageIcon, MessageSquare, Video } from 'lucide-react'

import { videoTaskApi } from '@/api/videoTask'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import VideoTaskCreateFormCompact from '@/pages/video-tasks/components/create-form-compact'
import type { VideoModel, VideoDuration } from '@/types/video-task'

import ChatInput from './chat-input'

export type CreativeInputMode = 'chat' | 'image_gen' | 'video'

/** 无 session 时创建视频任务的参数（由父组件先建会话再调 API） */
export interface VideoCreateParams {
  promptText: string
  model: VideoModel
  duration: VideoDuration
  referenceImages: string[]
}

export interface UnifiedInputAreaProps {
  /** 当前创作模式 */
  creativeMode: CreativeInputMode
  onCreativeModeChange: (mode: CreativeInputMode) => void
  /** 当前会话 ID（无则处于新建对话） */
  sessionId: string | undefined
  /** 对话模式：输入与发送 */
  chatValue: string
  chatOnChange: (value: string) => void
  chatOnSend: () => void
  chatIsLoading: boolean
  /** 参考图 URL（每行一个 http(s)），对话视觉与生图共用 */
  referenceImageUrls: string
  onReferenceImageUrlsChange: (value: string) => void
  /** 工具栏左侧额外（如模型选择器） */
  toolbarLeftExtra?: React.ReactNode
  /** 视频模式：有 session 时创建成功 / 无权限回调 */
  onVideoTaskCreated?: () => void
  onVideoSessionForbidden?: () => void
  /** 无 session 时用户点创建：父组件先建会话再创建任务后调用 onVideoTaskCreated 或导航 */
  onVideoCreateWithoutSession?: (params: VideoCreateParams) => Promise<void>
}

export default function UnifiedInputArea({
  creativeMode,
  onCreativeModeChange,
  sessionId,
  chatValue,
  chatOnChange,
  chatOnSend,
  chatIsLoading,
  referenceImageUrls,
  onReferenceImageUrlsChange,
  toolbarLeftExtra,
  onVideoTaskCreated,
  onVideoSessionForbidden,
  onVideoCreateWithoutSession,
}: Readonly<UnifiedInputAreaProps>): React.JSX.Element {
  const [showRefField, setShowRefField] = useState(false)

  const isChat = creativeMode === 'chat'
  const isImageGen = creativeMode === 'image_gen'
  const isVideo = creativeMode === 'video'

  const { data: videoCatalog } = useQuery({
    queryKey: ['video-tasks', 'models'],
    queryFn: () => videoTaskApi.listModels(),
    staleTime: 60_000,
    enabled: isVideo,
  })

  const parsedRefUrls = useMemo(() => {
    return referenceImageUrls
      .split('\n')
      .map((s) => s.trim())
      .filter((url) => url.startsWith('http://') || url.startsWith('https://'))
  }, [referenceImageUrls])

  const inputContent =
    isChat || isImageGen ? (
      <div className="space-y-2">
        {(isChat || isImageGen) && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between px-0.5">
              <button
                type="button"
                onClick={() => {
                  setShowRefField((v) => !v)
                }}
                className={cn(
                  'text-xs underline-offset-2 hover:underline',
                  parsedRefUrls.length > 0 ? 'text-primary' : 'text-muted-foreground'
                )}
              >
                {showRefField ? '隐藏参考图' : '参考图（URL）'}
                {parsedRefUrls.length > 0 ? ` · ${String(parsedRefUrls.length)} 张` : ''}
              </button>
              {isImageGen && (
                <span className="text-[11px] text-muted-foreground">图生图仅使用首张 URL</span>
              )}
            </div>
            {showRefField && (
              <Textarea
                value={referenceImageUrls}
                onChange={(e) => {
                  onReferenceImageUrlsChange(e.target.value)
                }}
                placeholder="每行一个图片 URL（https://...）"
                className="min-h-[72px] resize-y text-sm"
                disabled={chatIsLoading}
              />
            )}
          </div>
        )}
        <ChatInput
          value={chatValue}
          onChange={chatOnChange}
          onSend={chatOnSend}
          isLoading={chatIsLoading}
          toolbarLeftExtra={toolbarLeftExtra}
          placeholder={isImageGen ? '描述要生成的图像…' : '给 AI Agent 发送消息…'}
        />
      </div>
    ) : isVideo ? (
      <VideoTaskCreateFormCompact
        sessionId={sessionId}
        catalogModels={videoCatalog}
        onTaskCreated={onVideoTaskCreated}
        onSessionForbidden={onVideoSessionForbidden}
        onVideoCreateWithoutSession={onVideoCreateWithoutSession}
        disabled={chatIsLoading}
      />
    ) : null

  return (
    <div className="space-y-2">
      <div className="flex justify-center gap-0.5 rounded-full bg-muted/40 p-0.5">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            onCreativeModeChange('chat')
          }}
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
          onClick={() => {
            onCreativeModeChange('image_gen')
          }}
          className={cn(
            'h-7 rounded-full px-3 text-xs font-medium',
            isImageGen
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <ImageIcon className="mr-1.5 h-3.5 w-3.5" />
          生图
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            onCreativeModeChange('video')
          }}
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
      {(isVideo || isImageGen) && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => {
              onCreativeModeChange('chat')
            }}
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
