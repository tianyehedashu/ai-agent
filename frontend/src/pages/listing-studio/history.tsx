/**
 * Listing 创作 - 历史记录列表（独立页面）
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { listingStudioApi } from '@/api/listing-studio'
import { Button } from '@/components/ui/button'
import { JOB_STATUS_LABEL } from '@/constants/listing-studio'
import { ArrowLeft, Package } from '@/lib/lucide-icons'
import type { ListingStudioJob } from '@/types/listing-studio'

export default function ListingStudioHistoryPage(): React.JSX.Element {
  const { data, isLoading } = useQuery({
    queryKey: ['listing-studio', 'jobs'],
    queryFn: () => listingStudioApi.listJobs({ limit: 100 }),
  })
  const jobs = data?.items ?? []

  return (
    <div className="flex h-full flex-col overflow-auto bg-background">
      <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
        <header className="mb-8 flex items-center gap-4">
          <Button asChild variant="ghost" size="sm" className="rounded-xl">
            <Link to="/listing-studio">
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
              <p className="text-sm text-muted-foreground">Listing 创作生成的历史执行记录</p>
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
              {jobs.map((job: ListingStudioJob) => (
                <li key={job.id}>
                  <Link
                    to={`/listing-studio/history/${job.id}`}
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
