import type { ReactNode } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { useUserStore } from '@/stores/user'

interface RequirePlatformAdminProps {
  children: ReactNode
}

/** 仅平台管理员（role === admin）可访问的内容 */
export function RequirePlatformAdmin({
  children,
}: Readonly<RequirePlatformAdminProps>): React.JSX.Element {
  const { currentUser } = useUserStore()
  const isAdmin = currentUser?.role === 'admin'

  if (!isAdmin) {
    return (
      <div className="container max-w-3xl py-8">
        <Alert variant="destructive">
          <AlertDescription>需要平台管理员权限</AlertDescription>
        </Alert>
      </div>
    )
  }

  return <>{children}</>
}
