/**
 * 产品信息 - 历史记录列表（独立页面）
 */

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Package } from 'lucide-react'
import { Link } from 'react-router-dom'

import { productInfoApi } from '@/api/productInfo'
import { Button } from '@/components/ui/button'
import { JOB_STATUS_LABEL } from '@/constants/product-info'
import type { ProductInfoJob } from '@/types/product-info'

export default function ProductInfoHistoryPage(): React.JSX.Element {
  const { data, isLoading } = useQuery({
    queryKey: ['product-info', 'jobs'],
    queryFn: () => productInfoApi.listJobs({ limit: 100 }),
  })
  const jobs = data?.items ?? []

  return (
    <div className="flex h-full flex-col overflow-auto bg-background">
      <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
        <header className="mb-8 flex items-center gap-4">
          <Button asChild variant="ghost" size="sm" className="rounded-xl">
            <Link to="/product-info">
              <ArrowLeft className="h-4 w-4" />
              <span className="ml-1">返回</span>
            </Link>
          </Button>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
              <Package className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">历史记录</h1>
              <p className="text-sm text-muted-foreground">产品信息生成的历史执行记录</p>
            </div>
          </div>
        </header>

        <div className="rounded-2xl border border-border/60 bg-card">
          {isLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">加载中…</p>
          ) : jobs.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">暂无记录</p>
          ) : (
            <ul className="divide-y divide-border/60">
              {jobs.map((job: ProductInfoJob) => (
                <li key={job.id}>
                  <Link
                    to={`/product-info/history/${job.id}`}
                    className="flex items-center justify-between px-4 py-3 transition-colors hover:bg-muted/50"
                  >
                    <span className="truncate font-medium">{job.title ?? job.id}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {JOB_STATUS_LABEL[job.status] ?? job.status}
                      {job.created_at && (
                        <span className="ml-2">{new Date(job.created_at).toLocaleString()}</span>
                      )}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
