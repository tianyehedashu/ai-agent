/**
 * 任务选择/创建：当前 Job 展示、新建、切换
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { PlusCircle, FolderOpen } from 'lucide-react'

import { productInfoApi } from '@/api/productInfo'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { JOB_STATUS_LABEL } from '@/constants/product-info'
import { useToast } from '@/hooks/use-toast'
import type { ProductInfoJob } from '@/types/product-info'

interface JobSelectorProps {
  jobs: ProductInfoJob[]
  currentJobId: string | null
  onSelectJobId: (id: string | null) => void
  isLoading?: boolean
}

export function JobSelector({
  jobs,
  currentJobId,
  onSelectJobId,
  isLoading,
}: JobSelectorProps): React.JSX.Element {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const createMutation = useMutation({
    mutationFn: () => productInfoApi.createJob({ title: '产品信息' }),
    onSuccess: (job) => {
      void queryClient.invalidateQueries({ queryKey: ['product-info', 'jobs'] })
      onSelectJobId(job.id)
      toast({ title: '已创建新任务' })
    },
    onError: (err) => {
      toast({ title: '创建失败', description: String(err), variant: 'destructive' })
    },
  })

  const current = jobs.find((j) => j.id === currentJobId)
  const statusLabel = current ? (JOB_STATUS_LABEL[current.status] ?? current.status) : null

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2">
        <FolderOpen className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">当前任务</span>
      </div>
      <Select
        value={currentJobId ?? ''}
        onValueChange={(v) => {
          onSelectJobId(v === '' ? null : v)
        }}
        disabled={isLoading}
      >
        <SelectTrigger className="w-[280px] rounded-xl border-border/60">
          <SelectValue placeholder="选择或新建任务" />
        </SelectTrigger>
        <SelectContent>
          {jobs.map((job) => (
            <SelectItem key={job.id} value={job.id}>
              <span className="truncate">{job.title ?? job.id}</span>
              <span className="ml-1 text-muted-foreground">
                ({JOB_STATUS_LABEL[job.status] ?? job.status})
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="rounded-xl"
        onClick={() => {
          createMutation.mutate()
        }}
        disabled={(isLoading ?? false) || createMutation.isPending}
      >
        <PlusCircle className="h-4 w-4" />
        <span className="ml-1">新建任务</span>
      </Button>
      {statusLabel && (
        <span className="rounded-lg bg-muted/80 px-2.5 py-1 text-xs text-muted-foreground">
          {statusLabel}
        </span>
      )}
    </div>
  )
}
