/**
 * 历史任务详情抽屉：展示 Job 下所有步骤的输入/输出、文案、图片、提示词
 */

import { useQuery } from '@tanstack/react-query'

import { productInfoApi } from '@/api/productInfo'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { JOB_STATUS_LABEL } from '@/constants/product-info'

import { StepOutputView } from './step-output-view'

interface JobDetailDrawerProps {
  jobId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function JobDetailDrawer({
  jobId,
  open,
  onOpenChange,
}: JobDetailDrawerProps): React.JSX.Element {
  const { data: job, isLoading } = useQuery({
    queryKey: ['product-info', 'job', jobId],
    queryFn: () => {
      if (!jobId) throw new Error('job id required')
      return productInfoApi.getJob(jobId)
    },
    enabled: open && !!jobId,
  })

  const stepsByOrder = job?.steps ? [...job.steps].sort((a, b) => a.sort_order - b.sort_order) : []

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-hidden sm:max-w-2xl" side="right">
        <SheetHeader className="space-y-1">
          <SheetTitle className="tracking-tight">
            {job ? (job.title ?? job.id) : '任务详情'}
            {job && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                {JOB_STATUS_LABEL[job.status] ?? job.status}
              </span>
            )}
          </SheetTitle>
        </SheetHeader>
        <ScrollArea className="mt-5 h-[calc(100vh-8rem)] pr-4">
          {isLoading && <p className="text-sm text-muted-foreground">加载中…</p>}
          {!isLoading && job && (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                创建于 {job.created_at ? new Date(job.created_at).toLocaleString() : '—'}
              </p>
              {stepsByOrder.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无步骤记录</p>
              ) : (
                stepsByOrder.map((step) => (
                  <StepOutputView key={step.id} step={step} defaultExpanded={true} />
                ))
              )}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
