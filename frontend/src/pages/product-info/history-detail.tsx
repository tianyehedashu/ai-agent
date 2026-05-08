/**
 * 产品信息 - 单条历史记录详情（独立页面）
 */

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { productInfoApi } from '@/api/productInfo'
import { Button } from '@/components/ui/button'
import { JOB_STATUS_LABEL } from '@/constants/product-info'

import { StepOutputView } from './components/step-output-view'

export default function ProductInfoHistoryDetailPage(): React.JSX.Element {
  const { id } = useParams<{ id: string }>()
  const { data: job, isLoading } = useQuery({
    queryKey: ['product-info', 'job', id],
    queryFn: () => {
      if (!id) throw new Error('job id required')
      return productInfoApi.getJob(id)
    },
    enabled: !!id,
  })

  const stepsByOrder = job?.steps ? [...job.steps].sort((a, b) => a.sort_order - b.sort_order) : []

  return (
    <div className="flex h-full flex-col overflow-auto bg-background">
      <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
        <header className="mb-6 flex items-center gap-4">
          <Button asChild variant="ghost" size="sm" className="rounded-xl">
            <Link to="/product-info/history">
              <ArrowLeft className="h-4 w-4" />
              <span className="ml-1">返回列表</span>
            </Link>
          </Button>
        </header>

        {isLoading && <p className="text-sm text-muted-foreground">加载中…</p>}
        {!isLoading && !job && <p className="text-sm text-muted-foreground">记录不存在</p>}
        {!isLoading && job && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-border/60 bg-card p-5">
              <h1 className="font-semibold tracking-tight">
                {job.title ?? job.id}
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  {JOB_STATUS_LABEL[job.status] ?? job.status}
                </span>
              </h1>
              <p className="mt-1 text-xs text-muted-foreground">
                创建于 {job.created_at ? new Date(job.created_at).toLocaleString() : '—'}
              </p>
            </div>
            <div className="space-y-4">
              {stepsByOrder.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无步骤记录</p>
              ) : (
                stepsByOrder.map((step) => (
                  <StepOutputView key={step.id} step={step} defaultExpanded={true} />
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
