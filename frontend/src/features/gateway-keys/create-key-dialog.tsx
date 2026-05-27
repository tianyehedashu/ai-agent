import { useState } from 'react'

import { Link } from 'react-router-dom'

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
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/hooks/use-toast'
import { Copy } from '@/lib/lucide-icons'

export interface CreateKeyValues {
  name: string
  store_full_messages: boolean
  rpm_limit?: number | null
  tpm_limit?: number | null
}

export interface CreateKeyDialogProps {
  open: boolean
  teamId: string
  teamDisplayName: string
  onOpenChange: (open: boolean) => void
  onSubmit: (values: CreateKeyValues) => void
  plaintext: string | null
  createdKeyId: string | null
}

export function CreateKeyDialog({
  open,
  teamId,
  teamDisplayName,
  onOpenChange,
  onSubmit,
  plaintext,
  createdKeyId,
}: Readonly<CreateKeyDialogProps>): React.JSX.Element {
  const [values, setValues] = useState<CreateKeyValues>({
    name: '',
    store_full_messages: false,
  })
  const { toast } = useToast()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>创建虚拟 Key</DialogTitle>
          <DialogDescription>
            创建后请立即复制保存；之后仍可在列表中通过「查看」再次获取完整 Key。
          </DialogDescription>
        </DialogHeader>
        {plaintext ? (
          <div className="space-y-3 py-2">
            <Label className="text-xs text-muted-foreground">明文 Key（仅本次显示）</Label>
            <div className="flex items-center gap-2">
              <Input readOnly value={plaintext} className="font-mono text-xs" />
              <Button
                size="icon"
                variant="outline"
                onClick={() => {
                  void navigator.clipboard.writeText(plaintext)
                  toast({ title: '已复制' })
                }}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            {createdKeyId ? (
              <Button variant="outline" className="w-full" asChild>
                <Link
                  to={`/gateway/guide?key_id=${createdKeyId}#clients`}
                  state={{ vkeyPlain: plaintext, vkeyId: createdKeyId }}
                >
                  打开调用指南
                </Link>
              </Button>
            ) : null}
          </div>
        ) : (
          <div className="space-y-3 py-2">
            <div className="rounded-md border bg-muted/20 px-3 py-2 text-sm">
              <span className="text-muted-foreground">绑定团队：</span>
              <span className="font-medium">{teamDisplayName}</span>
              <span className="mt-1 block font-mono text-xs text-muted-foreground" title={teamId}>
                {teamId}
              </span>
            </div>
            <div>
              <Label htmlFor="key-name">名称</Label>
              <Input
                id="key-name"
                placeholder="生产环境 / SDK 客户端 / ..."
                value={values.name}
                onChange={(e) => {
                  setValues({ ...values, name: e.target.value })
                }}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="rpm">每分钟请求数上限（留空不限）</Label>
                <Input
                  id="rpm"
                  type="number"
                  value={values.rpm_limit ?? ''}
                  onChange={(e) => {
                    setValues({
                      ...values,
                      rpm_limit: e.target.value ? Number(e.target.value) : null,
                    })
                  }}
                />
              </div>
              <div>
                <Label htmlFor="tpm">每分钟令牌数上限（留空不限）</Label>
                <Input
                  id="tpm"
                  type="number"
                  value={values.tpm_limit ?? ''}
                  onChange={(e) => {
                    setValues({
                      ...values,
                      tpm_limit: e.target.value ? Number(e.target.value) : null,
                    })
                  }}
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="store" className="flex flex-col gap-1">
                <span>记录完整消息</span>
                <span className="text-xs text-muted-foreground">
                  关闭后仅存元数据（用于合规场景）
                </span>
              </Label>
              <Switch
                id="store"
                checked={values.store_full_messages}
                onCheckedChange={(v) => {
                  setValues({ ...values, store_full_messages: v })
                }}
              />
            </div>
          </div>
        )}
        <DialogFooter>
          {plaintext ? (
            <Button
              onClick={() => {
                onOpenChange(false)
              }}
            >
              完成
            </Button>
          ) : (
            <>
              <Button
                variant="ghost"
                onClick={() => {
                  onOpenChange(false)
                }}
              >
                取消
              </Button>
              <Button
                onClick={() => {
                  if (!values.name) return
                  onSubmit(values)
                }}
                disabled={!values.name}
              >
                创建
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
