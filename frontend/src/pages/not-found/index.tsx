import { Link } from 'react-router-dom'
import { Home } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center">
      <h1 className="text-9xl font-bold text-muted-foreground/20">404</h1>
      <h2 className="mt-4 text-2xl font-semibold">页面未找到</h2>
      <p className="mt-2 text-muted-foreground">
        抱歉，您访问的页面不存在
      </p>
      <Button asChild className="mt-6">
        <Link to="/">
          <Home className="mr-2 h-4 w-4" />
          返回首页
        </Link>
      </Button>
    </div>
  )
}
